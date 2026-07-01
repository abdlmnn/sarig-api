import uuid
from django.db import models
from apps.users.models import User
from decimal import Decimal
from apps.users.geo import to_wkt_point
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point


class StoreDeliveryTime(models.TextChoices):
    MORNING = "MORNING", "Morning"
    AFTERNOON = "AFTERNOON", "Afternoon"
    EVENING = "EVENING", "Evening"
    ALL_DAY = "ALL_DAY", "All day"


class BusinessVertical(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    allowed_product_types = models.JSONField(default=list, blank=True)
    requires_license = models.BooleanField(default=False)
    required_documents = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Business Vertical"
        verbose_name_plural = "Business Verticals"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="stores",
    )
    vertical = models.ForeignKey(
        BusinessVertical,
        on_delete=models.PROTECT,
        related_name="stores",
    )
    name = models.CharField(max_length=255)
    branch_name = models.CharField(max_length=120, blank=True)
    company_email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    delivery_time = models.CharField(max_length=20, choices=StoreDeliveryTime.choices, default=StoreDeliveryTime.ALL_DAY)
    
    # Coordinates (DecimalField for now as per user request)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    location_wkt = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    location_point = gis_models.PointField(geography=True, null=True, blank=True)
    
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    barangay = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    pinned_address = models.TextField(blank=True)
    
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
    )
    is_open = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    auto_accept_orders = models.BooleanField(default=False)
    
    # Metadata
    image = models.ImageField(upload_to="stores/", null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("5.00"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["is_open"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"

    def save(self, *args, **kwargs):
        self.location_wkt = to_wkt_point(self.latitude, self.longitude)
        if (
            getattr(settings, "USE_POSTGIS", False)
            and self.latitude is not None
            and self.longitude is not None
        ):
            self.location_point = Point(float(self.longitude), float(self.latitude), srid=4326)
        super().save(*args, **kwargs)
