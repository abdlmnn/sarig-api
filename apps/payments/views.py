from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import transaction
from django.conf import settings
import hmac
import hashlib
import logging
from .models import PaymentTransaction, PaymentStatus
from .services import PayMongoService
from apps.orders.models import OrderStatus
from apps.users.notifications import PushNotificationService

logger = logging.getLogger(__name__)


class PaymentMethodsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "paymongo": {
                    "enabled_methods": PayMongoService.get_enabled_payment_methods()
                }
            }
        )


class PayMongoWebhookView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "payment_webhook"

    PAID_EVENTS = {"payment.paid", "checkout_session.payment.paid"}
    FAILED_EVENTS = {"payment.failed", "checkout_session.payment.failed"}
    EXPIRED_EVENTS = {"checkout_session.expired", "checkout_session.payment.expired"}

    @transaction.atomic
    def post(self, request):
        raw_body = request.body
        payload = request.data

        signature = request.headers.get("Paymongo-Signature")
        if not self._is_valid_signature(raw_body, signature):
            return Response({"error": "Unauthorized"}, status=403)

        event_type, data_object = self._extract_event(payload)
        external_id = data_object.get("id")
        payment_id = self._extract_payment_id(data_object)

        if not external_id:
            return Response({"error": "No ID found in payload"}, status=400)

        try:
            payment_tx = self._get_transaction(data_object, external_id, payment_id)
        except PaymentTransaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=404)

        # Save raw response for audit
        payment_tx.provider_raw_response = payload

        # Idempotency Check: Don't process if already successful
        if payment_tx.status in {PaymentStatus.SUCCESS, PaymentStatus.REFUNDED}:
            return Response({"status": "Duplicate webhook ignored"}, status=200)

        if event_type in self.PAID_EVENTS:
            # Extract actual payment ID for future refunds
            if payment_id:
                payment_tx.payment_id = payment_id

            payment_tx.status = PaymentStatus.SUCCESS
            payment_tx.save()

            # The money is secure! Now we secure the inventory.
            from apps.catalog.services import InventoryService

            success, message = InventoryService.deduct_stock_for_order(
                payment_tx.order.id
            )

            if success:
                # Inventory deducted cleanly!
                order = payment_tx.order
                # Note: We NO LONGER set OrderStatus.ACCEPTED here.
                # The order stays PENDING (Merchant Approval) even if paid.
                order.save()

                # Trigger real-time alert to Merchant
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                channel_layer = get_channel_layer()
                store_group = f"store_{order.store.id}_orders"

                try:
                    async_to_sync(channel_layer.group_send)(
                        store_group,
                        {
                            "type": "order_alert",
                            "message": {
                                "order_id": str(order.id),
                                "total_amount": str(order.total_amount),
                                "customer_name": order.customer.get_full_name()
                                or order.customer.username,
                            },
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to broadcast paid order alert for order %s: %s",
                        order.id,
                        exc,
                    )

                # Handle Auto-Acceptance
                # Notify Merchant (Push Notification)
                from apps.users.notifications import PushNotificationService

                PushNotificationService.notify_new_order(order.store.owner, order.id)

                if order.store.auto_accept_orders:
                    order.status = OrderStatus.ACCEPTED
                    order.save()
                    order.broadcast_status_update()
                else:
                    # Schedule auto-cancellation in 5 minutes (if merchant doesn't accept manually)
                    from apps.orders.tasks import auto_cancel_stale_order

                    transaction.on_commit(
                        lambda: auto_cancel_stale_order.apply_async(
                            (str(order.id),), countdown=600
                        )
                    )
            else:
                # DISASTER AVERTED!
                # The item sold out while they were paying GCash.
                # We mark the order as cancelled, and we trigger the refund process.
                order = payment_tx.order
                order.status = OrderStatus.CANCELLED
                order.save()
                order.broadcast_status_update()

                self._attempt_refund_and_notify(
                    payment_tx=payment_tx,
                    customer=order.customer,
                    order_id=order.id,
                    reason="inventory_conflict",
                )

        elif event_type in self.FAILED_EVENTS:
            payment_tx.status = PaymentStatus.FAILED
            payment_tx.save()

            order = payment_tx.order
            order.status = OrderStatus.CANCELLED
            order.save()
            order.broadcast_status_update()

        elif event_type in self.EXPIRED_EVENTS:
            payment_tx.status = PaymentStatus.EXPIRED
            payment_tx.save()

            order = payment_tx.order
            order.status = OrderStatus.CANCELLED
            order.save()
            order.broadcast_status_update()

        return Response({"status": "Webhook received"})

    def _extract_event(self, payload):
        event_attributes = payload.get("data", {}).get("attributes", {})
        return event_attributes.get("type"), event_attributes.get("data", {})

    def _extract_payment_id(self, data_object):
        attributes = data_object.get("attributes", {})
        payments = attributes.get("payments") or []
        if attributes.get("payment_id"):
            return attributes["payment_id"]
        if payments and isinstance(payments[0], dict):
            return payments[0].get("id")
        if data_object.get("type") == "payment":
            return data_object.get("id")
        return None

    def _get_transaction(self, data_object, external_id, payment_id):
        transaction_qs = PaymentTransaction.objects.select_related(
            "order", "order__store", "order__customer"
        )
        payment_tx = transaction_qs.filter(external_transaction_id=external_id).first()
        if payment_tx:
            return payment_tx
        if payment_id:
            payment_tx = transaction_qs.filter(payment_id=payment_id).first()
            if payment_tx:
                return payment_tx
        order_id = data_object.get("attributes", {}).get("metadata", {}).get("order_id")
        if order_id:
            payment_tx = transaction_qs.filter(
                order_id=order_id, status=PaymentStatus.PENDING
            ).first()
            if payment_tx:
                return payment_tx
        raise PaymentTransaction.DoesNotExist

    def _attempt_refund_and_notify(self, payment_tx, customer, order_id, reason):
        if payment_tx.status == PaymentStatus.REFUNDED:
            PushNotificationService.notify_order_status(customer, "REFUNDED", order_id)
            return
        if payment_tx.payment_method != "PAYMONGO" or not payment_tx.payment_id:
            PushNotificationService.notify_order_status(customer, "CANCELLED", order_id)
            return
        try:
            PayMongoService.create_refund(
                payment_id=payment_tx.payment_id,
                amount=payment_tx.amount,
                reason="requested_by_customer",
            )
            payment_tx.status = PaymentStatus.REFUNDED
            payment_tx.save(update_fields=["status", "updated_at"])
            PushNotificationService.notify_order_status(customer, "REFUNDED", order_id)
        except Exception:
            PushNotificationService.notify_order_status(customer, "CANCELLED", order_id)

    def _is_valid_signature(self, payload_body, signature_header):
        secret = getattr(settings, "PAYMONGO_WEBHOOK_SECRET", "") or ""
        if not secret:
            return bool(settings.DEBUG)
        if not signature_header:
            return False
        digest = hmac.new(
            secret.encode("utf-8"), payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, signature_header.strip())
