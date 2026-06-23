import uuid
import logging
from django.db import models
from django.conf import settings
from apps.vendors.models import Store
from apps.catalog.models import Product


logger = logging.getLogger(__name__)


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Merchant Approval"
    ACCEPTED = "ACCEPTED", "Accepted by Merchant"
    PREPARING = "PREPARING", "Food is Preparing"
    READY = "READY", "Ready for Pickup"
    ON_THE_WAY = "ON_THE_WAY", "Rider on the way"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryMethod(models.TextChoices):
    DELIVERY = "DELIVERY", "Home Delivery"
    PICKUP = "PICKUP", "Self-Pickup"


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.DELIVERY,
        db_index=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="placed_orders",
    )
    store = models.ForeignKey(
        Store, on_delete=models.PROTECT, related_name="received_orders"
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    delivery_address_text = models.TextField()
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2)
    system_fee = models.DecimalField(max_digits=6, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Marketing
    promo_code = models.ForeignKey(
        "marketing.PromoCode", on_delete=models.SET_NULL, null=True, blank=True
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    estimated_arrival_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{str(self.id)[:8]} - {self.store.name} - {self.status}"

    def broadcast_status_update(self):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        try:
            # 1. Notify Tracking Group (Mobile Map)
            async_to_sync(channel_layer.group_send)(
                f"order_{self.id}",
                {
                    "type": "status_update",
                    "status": self.status,
                }
            )

            # 2. Notify Chat Group (To close the chat UI)
            async_to_sync(channel_layer.group_send)(
                f"chat_{self.id}",
                {
                    "type": "chat_message",
                    "message": f"SYSTEM: Order is {self.status}. Chat is now closed.",
                    "sender": "System",
                    "timestamp": str(self.updated_at)
                }
            )
        except Exception as exc:
            logger.warning("Failed to broadcast order status update for order %s: %s", self.id, exc)


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = models.TextField(blank=True, null=True)

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order {str(self.order.id)[:8]})"
