from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.orders.models import Order, OrderItem, OrderStatus
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus
from apps.payments.services import PayMongoService
from apps.catalog.models import Product
from apps.vendors.models import Store
from .serializers import OrderSerializer


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data
        user = request.user

        # 1. Validation (Basic)
        store_id = data.get("store_id")
        items_data = data.get("items", [])
        
        if not store_id or not items_data:
            return Response(
                {"error": "Store ID and items are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        store = get_object_or_404(Store, id=store_id)

        # 2. Create the Order
        # In a real app, calculate totals server-side for security
        order = Order.objects.create(
            customer=user,
            store=store,
            delivery_address_text=data.get("address_text", ""),
            delivery_latitude=data.get("latitude", 0),
            delivery_longitude=data.get("longitude", 0),
            subtotal=data.get("subtotal", 0),
            delivery_fee=data.get("delivery_fee", 0),
            system_fee=data.get("system_fee", 0),
            total_amount=data.get("total_amount", 0)
        )

        # 3. Create Order Items
        for item in items_data:
            product = get_object_or_404(Product, id=item["product_id"])
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item["quantity"],
                unit_price=product.price,
                special_instructions=item.get("special_instructions", "")
            )

        # 4. Handle Payment Logic
        requested_method = data.get("payment_method")

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
