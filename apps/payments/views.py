from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import transaction
from django.conf import settings
import hmac
import hashlib
from .models import PaymentTransaction, PaymentStatus
from apps.orders.models import OrderStatus


class PayMongoWebhookView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        raw_body = request.body
        payload = request.data
        
        signature = request.headers.get('Paymongo-Signature')
        if not self._is_valid_signature(raw_body, signature):
            return Response({"error": "Unauthorized"}, status=403)

        event_type = payload.get('data', {}).get('attributes', {}).get('type')
        
        # The structure of PayMongo webhook payload can vary depending on the event
        # This is a simplified extraction
        data_object = payload.get('data', {}).get('attributes', {}).get('data', {})
        external_id = data_object.get('id')

        if not external_id:
            return Response({"error": "No ID found in payload"}, status=400)

        try:
            payment_tx = PaymentTransaction.objects.get(external_transaction_id=external_id)
        except PaymentTransaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=404)

        # Save raw response for audit
        payment_tx.provider_raw_response = payload

        # Idempotency Check: Don't process if already successful
        if payment_tx.status == PaymentStatus.SUCCESS:
            return Response({"status": "Duplicate webhook ignored"}, status=200)

        if event_type == 'payment.paid' or event_type == 'checkout_session.payment.paid':
            # Extract actual payment ID for future refunds
            payment_id = data_object.get('attributes', {}).get('payment_id')
            if payment_id:
                payment_tx.payment_id = payment_id
            
            payment_tx.status = PaymentStatus.SUCCESS
            payment_tx.save()

            # The money is secure! Now we secure the inventory.
            from apps.catalog.services import InventoryService
            success, message = InventoryService.deduct_stock_for_order(payment_tx.order.id)

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
                
                async_to_sync(channel_layer.group_send)(
                    store_group,
                    {
                        "type": "order_alert",
                        "message": {
                            "order_id": str(order.id),
                            "total_amount": str(order.total_amount),
                            "customer_name": order.customer.get_full_name() or order.customer.username,
                        }
                    }
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
                    auto_cancel_stale_order.apply_async((str(order.id),), countdown=600)
            else:
                # DISASTER AVERTED!
                # The item sold out while they were paying GCash.
                # We mark the order as cancelled, and we trigger the refund process.
                order = payment_tx.order
                order.status = OrderStatus.CANCELLED
                order.save()

                # TODO: Call PayMongo API to automatically refund the customer's GCash
                # TODO: Send a Push Notification apologizing to the customer.

        elif event_type == 'payment.failed':
            payment_tx.status = PaymentStatus.FAILED
            payment_tx.save()

            order = payment_tx.order
            order.status = OrderStatus.CANCELLED
            order.save()

        return Response({"status": "Webhook received"})

    def _is_valid_signature(self, payload_body, signature_header):
        secret = getattr(settings, "PAYMONGO_WEBHOOK_SECRET", "") or ""
        # If no secret is configured, keep non-blocking behavior for local/dev.
        if not secret:
            return True
        if not signature_header:
            return False
        digest = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature_header.strip())
