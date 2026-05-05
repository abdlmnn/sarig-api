import uuid
from django.db import models
from apps.orders.models import Order


class PaymentMethod(models.TextChoices):
    COD = "COD", "Cash on Delivery"
    STRIPE = "STRIPE", "Stripe (Card/Digital)"
    PAYMONGO = "PAYMONGO", "PayMongo (GCash/Maya/Card)"
    WALLET = "WALLET", "Internal Sarig Wallet"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending/Awaiting Payment"
    AUTHORIZED = "AUTHORIZED", "Authorized (Funds held, not captured)"
    SUCCESS = "SUCCESS", "Payment Successful"
    FAILED = "FAILED", "Payment Failed"
    REFUNDED = "REFUNDED", "Payment Refunded"


class PaymentTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="payment_attempts"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    external_transaction_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True, unique=True
    )
    provider_raw_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment_method} - {self.status} - ₱{self.amount} (Order: {str(self.order.id)[:8]})"
