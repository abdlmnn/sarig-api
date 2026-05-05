import uuid
from django.db import models
from django.utils import timezone
from decimal import Decimal

class DiscountType(models.TextChoices):
    PERCENTAGE = "PERCENTAGE", "Percentage (%)"
    FIXED = "FIXED", "Fixed Amount (₱)"

class PromoCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    
    discount_type = models.CharField(
        max_length=20, 
        choices=DiscountType.choices, 
        default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Constraints
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Validity
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    # Usage
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self, order_amount=0):
        now = timezone.now()
        
        if not self.is_active:
            return False, "This promo code is inactive."
        
        if now < self.start_date:
            return False, "This promo code has not started yet."
            
        if now > self.end_date:
            return False, "This promo code has expired."
            
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False, "This promo code has reached its usage limit."
            
        if Decimal(str(order_amount)) < self.min_order_amount:
            return False, f"Minimum order amount of ₱{self.min_order_amount} required."
            
        return True, ""

    def calculate_discount(self, order_amount):
        amount = Decimal(str(order_amount))
        
        if self.discount_type == DiscountType.PERCENTAGE:
            discount = amount * (self.discount_value / Decimal("100"))
            if self.max_discount_amount and discount > self.max_discount_amount:
                discount = self.max_discount_amount
        else:
            discount = self.discount_value
            
        # Ensure discount doesn't exceed order amount
        return min(discount, amount)

    def __str__(self):
        return f"{self.code} ({self.discount_value}{'%' if self.discount_type == DiscountType.PERCENTAGE else ' ₱'})"

    class Meta:
        ordering = ["-created_at"]
