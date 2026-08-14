import uuid
import os
from django.db import IntegrityError, models, transaction
from apps.users.models import User
from decimal import Decimal
from apps.users.geo import to_wkt_point
from django.conf import settings
from django.utils.text import slugify

if getattr(settings, "USE_POSTGIS", False):
    if os.name == "nt" and getattr(settings, "GDAL_LIBRARY_PATH", ""):
        os.add_dll_directory(os.path.dirname(settings.GDAL_LIBRARY_PATH))
    from django.contrib.gis.db import models as gis_models
    from django.contrib.gis.geos import Point
else:
    Point = None


class StoreDeliveryTime(models.TextChoices):
    MORNING = "MORNING", "Morning"
    AFTERNOON = "AFTERNOON", "Afternoon"
    EVENING = "EVENING", "Evening"
    ALL_DAY = "ALL_DAY", "All day"


class StoreManualOverride(models.TextChoices):
    OPEN_NOW = "OPEN_NOW", "Open now"
    CLOSED_TEMPORARILY = "CLOSED_TEMPORARILY", "Closed temporarily"
    PAUSED_ORDERS = "PAUSED_ORDERS", "Paused orders"


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
    slug = models.SlugField(max_length=280, unique=True, editable=False)
    branch_name = models.CharField(max_length=120, blank=True)
    company_email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    delivery_time = models.CharField(max_length=20, choices=StoreDeliveryTime.choices, default=StoreDeliveryTime.ALL_DAY)
    
    # Coordinates (DecimalField for now as per user request)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    location_wkt = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    if getattr(settings, "USE_POSTGIS", False):
        location_point = gis_models.PointField(geography=True, null=True, blank=True)
    else:
        location_point = models.JSONField(null=True, blank=True)
    
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
    business_hours = models.JSONField(default=list, blank=True)
    manual_override = models.CharField(
        max_length=30,
        choices=StoreManualOverride.choices,
        null=True,
        blank=True,
    )
    manual_override_reason = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    auto_accept_orders = models.BooleanField(default=False)
    
    # Metadata
    logo_image = models.ImageField(upload_to="stores/logos/", null=True, blank=True)
    banner_image = models.ImageField(upload_to="stores/banners/", null=True, blank=True)
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
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(slug=""),
                name="vendors_store_slug_not_blank",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"

    def save(self, *args, **kwargs):
        if self.pk:
            saved_slug = (
                Store.objects.filter(pk=self.pk)
                .values_list("slug", flat=True)
                .first()
            )
            if saved_slug:
                self.slug = saved_slug

        slug_created = False
        base_slug = ""
        if not self.slug:
            base_slug = slugify(self.name)[:260] or str(self.id)
            slug = base_slug
            if Store.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                branch_slug = slugify(self.branch_name)[:80]
                if branch_slug:
                    slug = f"{base_slug[:199]}-{branch_slug}"
            suffix = 2
            while Store.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug[:270 - len(str(suffix))]}-{suffix}"
                suffix += 1
            self.slug = slug
            slug_created = True
        if slug_created and kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = list(
                dict.fromkeys([*kwargs["update_fields"], "slug"])
            )
        self.location_wkt = to_wkt_point(self.latitude, self.longitude)
        if (
            getattr(settings, "USE_POSTGIS", False)
            and Point is not None
            and self.latitude is not None
            and self.longitude is not None
        ):
            self.location_point = Point(float(self.longitude), float(self.latitude), srid=4326)
        if not slug_created:
            return super().save(*args, **kwargs)

        try:
            with transaction.atomic():
                return super().save(*args, **kwargs)
        except IntegrityError:
            if not Store.objects.filter(slug=self.slug).exists():
                raise

        unique_suffix = str(self.id).replace("-", "")[:12]
        self.slug = f"{base_slug[:267]}-{unique_suffix}"
        return super().save(*args, **kwargs)
