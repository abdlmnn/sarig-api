import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class OrderReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order", 
        on_delete=models.CASCADE, 
        related_name="review"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name="submitted_reviews"
    )
    
    # Store Rating
    store = models.ForeignKey(
        "vendors.Store", 
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    store_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    store_comment = models.TextField(blank=True)
    
    # Rider Rating (Optional - if order had a rider)
    rider_profile = models.ForeignKey(
        "riders.RiderProfile", 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name="reviews"
    )
    rider_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, 
        blank=True
    )
    rider_comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for Order {str(self.order.id)[:8]} (Store: {self.store_rating}, Rider: {self.rider_rating})"

    class Meta:
        ordering = ["-created_at"]
