import json
import mimetypes
from datetime import timedelta

from rest_framework import status, permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import CharField, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.db.models.functions import Cast
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from apps.orders.models import (
    CustomerCart,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderPrescription,
    OrderStatus,
)
from apps.users.permissions import IsCustomer, IsMerchant
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus
from apps.payments.services import PayMongoService
from apps.vendors.models import Store
from apps.vendors.permissions import IsMerchantOrAdmin
from .serializers import CheckoutRequestSerializer, OrderSerializer
from .pricing import CheckoutPricingError, calculate_checkout_pricing
from .services import ACTIVE_STATUSES, build_store_order_activity, merchant_order_summary


logger = logging.getLogger(__name__)


class StoreOrderActivityView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def get(self, request):
        payload = build_store_order_activity(request)
        if payload is None:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        return Response(payload)


class MerchantOrderListView(APIView):
    permission_classes = [IsMerchant]

    def get(self, request):
        stores = list(request.user.stores.filter(is_active=True).order_by("name"))
        if not stores:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        status_filter = request.query_params.get("status", "ACTIVE").strip().upper()
        query = request.query_params.get("q", "").strip()
        orders = (
            Order.objects.filter(store_id__in=[store.id for store in stores])
            .select_related("customer", "rider", "store__vertical")
            .prefetch_related("items__product")
            .annotate(order_id_text=Cast("id", output_field=CharField()))
        )

        if status_filter == "ACTIVE":
            orders = orders.filter(status__in=ACTIVE_STATUSES)
        elif status_filter != "ALL":
            if status_filter not in OrderStatus.values:
                return Response(
                    {"detail": "Invalid order status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            orders = orders.filter(status=status_filter)

        orders = orders.order_by("created_at", "id")

        if query:
            order_query = query.upper().removeprefix("SRG-").strip()
            orders = orders.filter(
                Q(order_id_text__icontains=order_query)
                | Q(customer__first_name__icontains=query)
                | Q(customer__last_name__icontains=query)
                | Q(customer__username__icontains=query)
                | Q(items__product__name__icontains=query)
            ).distinct()

        return Response({
            "orders": [merchant_order_summary(order) for order in orders[:100]],
        })


class MerchantOrderDetailView(APIView):
    permission_classes = [IsMerchant]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related(
                "store__vertical",
                "customer",
                "rider",
                "rider__rider_profile",
            ).prefetch_related("items__product", "payment_attempts", "prescriptions"),
            id=order_id,
            store__owner=request.user,
        )

        return Response(OrderSerializer(order, context={"request": request}).data)


class CustomerOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related(
                "store__vertical",
                "customer",
                "rider",
                "rider__rider_profile",
            ).prefetch_related("items__product", "payment_attempts", "prescriptions"),
            id=order_id,
            customer=request.user,
        )

        return Response(OrderSerializer(order, context={"request": request}).data)


class PrescriptionFileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "files"

    def get(self, request, prescription_id):
        prescription = get_object_or_404(
            OrderPrescription.objects.select_related(
                "order", "order__store", "order__customer", "order__rider"
            ),
            id=prescription_id,
        )
        order = prescription.order
        user = request.user
        is_authorized = (
            user.is_staff
            or order.customer_id == user.id
            or order.rider_id == user.id
            or order.store.owner_id == user.id
        )
        if not is_authorized:
            return Response(
                {"detail": "You do not have access to this file."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not prescription.file:
            return Response(
                {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
            )
        file_name = prescription.file.name.rsplit("/", 1)[-1]
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        return FileResponse(
            prescription.file.open("rb"),
            as_attachment=request.query_params.get("download") == "1",
            filename=file_name,
            content_type=content_type,
        )


class MerchantStoreOrderAnalyticsView(APIView):
    permission_classes = [IsMerchantOrAdmin]

    def get(self, request, store_id):
        store = get_object_or_404(Store, id=store_id)

        if not request.user.is_staff and store.owner != request.user:
            return Response({"error": "You do not own this store."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)
        delivered_orders = Order.objects.filter(store=store, status=OrderStatus.DELIVERED)

        total_revenue = delivered_orders.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_orders = delivered_orders.count()
        today_revenue = delivered_orders.filter(created_at__gte=today_start).aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        today_orders = delivered_orders.filter(created_at__gte=today_start).count()
        top_products = (
            OrderItem.objects.filter(order__store=store, order__status=OrderStatus.DELIVERED)
            .values("product__name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )
        sales_trend = (
            delivered_orders.filter(created_at__gte=seven_days_ago)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(daily_revenue=Sum("total_amount"), daily_orders=Count("id"))
            .order_by("date")
        )

        return Response(
            {
                "overview": {
                    "total_revenue": float(total_revenue),
                    "total_orders": total_orders,
                    "today_revenue": float(today_revenue),
                    "today_orders": today_orders,
                },
                "top_products": top_products,
                "sales_trend": list(sales_trend),
            }
        )


class CheckoutQuoteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    throttle_scope = "checkout_quote"

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        store = get_object_or_404(Store, id=data["store_id"])
        try:
            pricing = calculate_checkout_pricing(store, data)
        except CheckoutPricingError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(pricing.quote_payload())


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_scope = "checkout"

    @transaction.atomic
    def post(self, request):
        data = request.data.copy()
        if "items_json" in data and "items" not in data:
            try:
                data["items"] = json.loads(data.get("items_json") or "[]")
                data.pop("items_json", None)
            except json.JSONDecodeError:
                return Response(
                    {"error": "Invalid checkout items."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if hasattr(request.FILES, "getlist"):
            prescription_files = request.FILES.getlist("prescription_files")
            if prescription_files:
                data.setlist("prescription_files", prescription_files)
        user = request.user

        serializer = CheckoutRequestSerializer(data=data)
        if not serializer.is_valid():
            errors = serializer.errors
            if "store_id" in errors or "items" in errors:
                return Response(
                    {"error": "Store ID and items are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"error": errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        data = serializer.validated_data
        store_id = data["store_id"]

        store = get_object_or_404(Store, id=store_id)

        try:
            pricing = calculate_checkout_pricing(
                store,
                data,
                lock_products=True,
            )
        except CheckoutPricingError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prescription_files = data.get("prescription_files", [])
        if pricing.requires_prescription and not prescription_files:
            return Response(
                {
                    "error": (
                        f"Product {pricing.prescription_product_name} "
                        "requires a prescription."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Create the Order
        order = Order.objects.create(
            customer=user,
            store=store,
            delivery_method=data["delivery_method"],
            delivery_option=data.get("delivery_option", "STANDARD"),
            delivery_address_text=data.get("address_text", ""),
            delivery_latitude=data.get("latitude", store.latitude),
            delivery_longitude=data.get("longitude", store.longitude),
            subtotal=pricing.subtotal,
            delivery_fee=pricing.delivery_fee,
            system_fee=pricing.system_fee,
            discount_amount=pricing.discount_amount,
            promo_code=pricing.promo,
            total_amount=pricing.total_amount,
        )

        # Increment usage count if order is created successfully
        if pricing.promo:
            type(pricing.promo).objects.filter(id=pricing.promo.id).update(
                usage_count=F("usage_count") + 1
            )

        # 5. Create Order Items
        for item in pricing.order_items:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                special_instructions=item["special_instructions"]
            )

        for prescription_file in prescription_files:
            OrderPrescription.objects.create(order=order, file=prescription_file)

        CustomerCart.objects.filter(
            customer=user,
            store=store,
        ).delete()

        # 4. Handle Payment Logic
        requested_method = data["payment_method"]

        if requested_method == PaymentMethod.COD:
            PaymentTransaction.objects.create(
                order=order,
                amount=order.total_amount,
                payment_method=PaymentMethod.COD,
                status=PaymentStatus.PENDING # COD is pending until delivery
            )
            
            # Trigger real-time alert to Merchant for COD
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
                            "customer_name": order.customer.get_full_name() or order.customer.username,
                        }
                    }
                )
            except Exception as exc:
                logger.warning("Failed to broadcast COD order alert for order %s: %s", order.id, exc)
            
            # Notify Merchant (Push Notification)
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_new_order(store.owner, order.id)

            # 5. Handle Auto-Acceptance
            if store.auto_accept_orders:
                order.status = OrderStatus.ACCEPTED
                order.save()
                order.broadcast_status_update()
            else:
                # Schedule auto-cancellation in 5 minutes (for manual acceptance)
                from .tasks import auto_cancel_stale_order
                transaction.on_commit(
                    lambda: auto_cancel_stale_order.apply_async(
                        (str(order.id),), countdown=600
                    )
                )

            return Response({
                "status": "success",
                "message": "Order placed via COD.",
                "order": OrderSerializer(order, context={"request": request}).data
            }, status=status.HTTP_201_CREATED)

        elif requested_method == PaymentMethod.PAYMONGO:
            transaction_record = PaymentTransaction.objects.create(
                order=order,
                amount=order.total_amount,
                payment_method=PaymentMethod.PAYMONGO,
                status=PaymentStatus.PENDING
            )

            # Call PayMongo API to generate a checkout link
            paymongo_response = PayMongoService.create_checkout_session(
                amount=order.total_amount,
                description=f"Sarig Order {order.id}",
                order_id=order.id,
            )

            transaction_record.external_transaction_id = paymongo_response['id']
            transaction_record.provider_raw_response = paymongo_response.get("raw")
            transaction_record.save(update_fields=["external_transaction_id", "provider_raw_response", "updated_at"])

            return Response({
                "status": "pending",
                "checkout_url": paymongo_response['checkout_url'],
                "order": OrderSerializer(order, context={"request": request}).data
            }, status=status.HTTP_201_CREATED)

        return Response(
            {"error": "Invalid payment method"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
class MerchantOrderActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "checkout"

    def post(self, request, order_id):
        action = request.data.get("action")
        order = get_object_or_404(Order, id=order_id)
        user = request.user

        # 1. Security Check: Does the user own this store?
        if not user.is_staff and order.store.owner != user:
            return Response(
                {"error": "You do not have permission to manage this order."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Logic Check: Can we perform this action?
        if action == "accept":
            if order.status != OrderStatus.PENDING:
                return Response(
                    {"error": f"Order cannot be accepted from {order.status} state."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = OrderStatus.ACCEPTED
            order.save()
            order.broadcast_status_update()

            # Notify Customer
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "ACCEPTED", order.id)

            # No Dispatcher here. Merchant is just acknowledging the order.
            
            return Response({
                "status": "success",
                "message": "Order accepted by merchant. Preparing food...",
                "order": OrderSerializer(order).data
            })

        elif action == "mark_preparing":
            if order.status != OrderStatus.ACCEPTED:
                return Response(
                    {"error": "Order must be 'Accepted' before marking as preparing."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            order.status = OrderStatus.PREPARING
            order.save()
            order.broadcast_status_update()

            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "PREPARING", order.id)

            if order.delivery_method == "DELIVERY":
                from apps.riders.services import RiderDispatcherService
                RiderDispatcherService.maybe_pre_dispatch_order(order)

            return Response({
                "status": "success",
                "message": "Order is now preparing.",
                "order": OrderSerializer(order).data
            })

        elif action == "mark_ready":
            if order.status not in [OrderStatus.ACCEPTED, OrderStatus.PREPARING]:
                return Response(
                    {"error": "Order must be accepted or preparing before marking as ready."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = OrderStatus.READY
            order.save()
            order.broadcast_status_update()

            # Notify Customer
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "READY", order.id)

            # TRIGGER DISPATCHER ONLY FOR HOME DELIVERY
            if order.delivery_method == "DELIVERY":
                from apps.riders.services import RiderDispatcherService
                RiderDispatcherService.dispatch_ready_order(order)
            else:
                # For PICKUP, just notify customer they can now walk to the store
                PushNotificationService.send_push(
                    order.customer,
                    "Order Ready for Pickup! 🎒",
                    f"Your order from {order.store.name} is ready. You can now head to the store!"
                )

            return Response({
                "status": "success",
                "message": "Order is ready for pickup. Finding a rider...",
                "order": OrderSerializer(order).data
            })

        elif action == "reject":
            if order.status not in [OrderStatus.PENDING, OrderStatus.ACCEPTED]:
                return Response(
                    {"error": "Order cannot be rejected at this stage."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                return Response(
                    {"error": "Reject reason is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(reason) > 500:
                return Response(
                    {"error": "Reject reason must be 500 characters or fewer."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            order.status = OrderStatus.CANCELLED
            order.cancel_reason = reason
            order.save(update_fields=["status", "cancel_reason", "updated_at"])
            order.broadcast_status_update()

            # Handle Automatic Refund for Paid Orders
            payment_tx = order.payment_attempts.filter(
                status=PaymentStatus.SUCCESS,
                payment_method=PaymentMethod.PAYMONGO
            ).first()

            refund_status = "No payment to refund"
            if payment_tx and payment_tx.payment_id:
                try:
                    PayMongoService.create_refund(
                        payment_id=payment_tx.payment_id,
                        amount=payment_tx.amount
                    )
                    payment_tx.status = PaymentStatus.REFUNDED
                    payment_tx.save()
                    refund_status = "Refund processed successfully"
                except Exception as e:
                    refund_status = f"Refund failed: {str(e)}"

            return Response({
                "status": "success",
                "message": "Order rejected/cancelled by merchant.",
                "refund_status": refund_status,
                "order": OrderSerializer(order).data
            })

        return Response(
            {"error": "Invalid action. Use 'accept', 'mark_preparing', 'mark_ready', or 'reject'."},
            status=status.HTTP_400_BAD_REQUEST
        )
