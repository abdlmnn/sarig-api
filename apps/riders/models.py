import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.users.geo import to_wkt_point

if getattr(settings, "USE_POSTGIS", False):
    from django.contrib.gis.db import models as gis_models
    from django.contrib.gis.geos import Point
else:
    Point = None

class RiderProfile(models.Model):
    VEHICLE_CHOICES = [
        ("MOTORCYCLE", "Motorcycle"),
        ("BICYCLE", "Bicycle"),
        ("CAR", "Car"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rider_profile"
    )
    
    is_online = models.BooleanField(default=False, db_index=True)
    is_available = models.BooleanField(default=True, db_index=True) # False if on a trip
    
    # Capability Flags
    can_do_delivery = models.BooleanField(default=True, db_index=True)
    can_do_ride_hailing = models.BooleanField(default=False, db_index=True)

    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_CHOICES,
        default="MOTORCYCLE"
    )
    plate_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Real-time Location
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_wkt = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    if getattr(settings, "USE_POSTGIS", False):
        location_point = gis_models.PointField(geography=True, null=True, blank=True)
    else:
        location_point = models.JSONField(null=True, blank=True)
    last_location_update = models.DateTimeField(auto_now=True)

    # Wallet
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Rider: {self.user.username} (Balance: ₱{self.balance})"

    class Meta:
        verbose_name = "Rider Profile"
        verbose_name_plural = "Rider Profiles"
        indexes = [
            models.Index(fields=["is_online", "is_available", "can_do_delivery"]),
            models.Index(fields=["is_online", "is_available", "can_do_ride_hailing"]),
        ]

    def save(self, *args, **kwargs):
        self.location_wkt = to_wkt_point(self.current_latitude, self.current_longitude)
        if (
            getattr(settings, "USE_POSTGIS", False)
            and Point is not None
            and self.current_latitude is not None
            and self.current_longitude is not None
        ):
            self.location_point = Point(float(self.current_longitude), float(self.current_latitude), srid=4326)
        super().save(*args, **kwargs)


class RiderTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("EARNING", "Delivery Earning"),
        ("WITHDRAWAL", "Cash Withdrawal"),
        ("BONUS", "Bonus"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE, related_name="transactions")
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_type} - ₱{self.amount} ({self.rider.user.username})"


class RiderOrderOfferStatus(models.TextChoices):
    OFFERED = "OFFERED", "Offered"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class RiderOrderOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="rider_offers",
    )
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name="order_offers",
    )
    status = models.CharField(
        max_length=20,
        choices=RiderOrderOfferStatus.choices,
        default=RiderOrderOfferStatus.OFFERED,
        db_index=True,
    )
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    offered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-offered_at"]
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["rider", "status"]),
            models.Index(fields=["expires_at", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status=RiderOrderOfferStatus.ACCEPTED),
                name="unique_accepted_rider_offer_per_order",
            ),
            models.UniqueConstraint(
                fields=["order", "rider"],
                condition=models.Q(status=RiderOrderOfferStatus.OFFERED),
                name="unique_active_rider_offer_per_rider_order",
            ),
        ]

    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"{self.order_id} -> {self.rider.user.username} ({self.status})"
