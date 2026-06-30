from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.db import transaction
from django.db.models import F
from decimal import Decimal
from django.shortcuts import get_object_or_404
import logging

from apps.orders.models import DeliveryMethod, Order, OrderItem, OrderStatus
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus
from apps.payments.services import PayMongoService
from apps.catalog.models import Product
from apps.vendors.models import Store
from .serializers import CheckoutRequestSerializer, OrderSerializer


logger = logging.getLogger(__name__)


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "checkout"

    @transaction.atomic
    def post(self, request):
        data = request.data
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
        items_data = data["items"]

        store = get_object_or_404(Store, id=store_id)

        # 2. Advanced Validation
        if not store.is_open or not store.is_active:
            return Response(
                {"error": "This store is currently closed or inactive."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Calculate Totals Server-Side (Security)
        calculated_subtotal = 0
        order_items_to_create = []

        for item_data in items_data:
            product = get_object_or_404(Product.objects.select_for_update(), id=item_data["product_id"])
            
            # Verify product belongs to store
            if product.category.store != store:
                return Response(
                    {"error": f"Product {product.name} does not belong to this store."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            qty = item_data["quantity"]
            if product.track_inventory and product.stock_quantity is not None and product.stock_quantity < qty:
                return Response(
                    {"error": f"Insufficient stock for {product.name}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            calculated_subtotal += product.price * qty
            
            order_items_to_create.append({
                "product": product,
                "quantity": qty,
                "unit_price": product.price,
                "special_instructions": item_data.get("special_instructions", "")
            })

        # Final amounts (CALCULATED ON SERVER FOR SECURITY)
        delivery_method = data["delivery_method"]
        
        # 1. System Fee (Flat 10 PHP)
        system_fee = Decimal("10.00")
        
        # 2. Delivery Fee (Base 40 + distance based)
        if delivery_method == DeliveryMethod.PICKUP:
            delivery_fee = Decimal("0.00")
        else:
            from apps.locations.services import calculate_delivery_fee, route_estimate

            estimate = route_estimate(
                {"latitude": store.latitude, "longitude": store.longitude},
                {"latitude": data["latitude"], "longitude": data["longitude"]},
            )
            if float(estimate["distance_km"]) > settings.DELIVERY_MAX_DISTANCE_KM:
                return Response(
                    {"error": "Delivery address is outside the supported distance."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            delivery_fee = calculate_delivery_fee(estimate["distance_km"])
        
        # --- Handle Promo Code ---
        promo_code_str = data.get("promo_code")
        promo_obj = None
        discount_amount = Decimal("0.00")
        
        if promo_code_str:
            from apps.marketing.models import PromoCode
            promo_obj = PromoCode.objects.filter(code__iexact=promo_code_str).first()
            if promo_obj:
                is_valid, error_msg = promo_obj.is_valid(calculated_subtotal)
                if not is_valid:
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                
                discount_amount = promo_obj.calculate_discount(calculated_subtotal)
            else:
                return Response({"error": "Invalid promo code."}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = (calculated_subtotal + Decimal(str(delivery_fee)) + Decimal(str(system_fee))) - discount_amount
        total_amount = max(total_amount, Decimal("0.00")) # Never negative

        # 4. Create the Order
        order = Order.objects.create(
            customer=user,
            store=store,
            delivery_method=delivery_method,
            delivery_address_text=data.get("address_text", ""),
            delivery_latitude=data["latitude"],
            delivery_longitude=data["longitude"],
            subtotal=calculated_subtotal,
            delivery_fee=delivery_fee,
            system_fee=system_fee,
            discount_amount=discount_amount,
            promo_code=promo_obj,
            total_amount=total_amount
        )

        # Increment usage count if order is created successfully
        if promo_obj:
            PromoCode.objects.filter(id=promo_obj.id).update(usage_count=F('usage_count') + 1)

        # 5. Create Order Items
        for item in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                special_instructions=item["special_instructions"]
            )

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
                auto_cancel_stale_order.apply_async((str(order.id),), countdown=600)

            return Response({
                "status": "success",
                "message": "Order placed via COD.",
                "order": OrderSerializer(order).data
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
                description=f"Sarig Order {order.id}"
            )

            transaction_record.external_transaction_id = paymongo_response['id']
            transaction_record.save()

            return Response({
                "status": "pending",
                "checkout_url": paymongo_response['checkout_url'],
                "order": OrderSerializer(order).data
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

        elif action == "mark_ready":
            if order.status != OrderStatus.ACCEPTED:
                return Response(
                    {"error": "Order must be 'Accepted' before marking as ready."},
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
                RiderDispatcherService.assign_rider_to_order(order)
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

            order.status = OrderStatus.CANCELLED
            order.save()
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
            {"error": "Invalid action. Use 'accept' or 'reject'."},
            status=status.HTTP_400_BAD_REQUEST
        )
