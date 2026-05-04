from django.db import models
from apps.users.models import User
from decimal import Decimal

# GDAL / POSTGIS (TEMPORARILY DISABLED FOR WINDOWS)
# from django.contrib.gis.db import models as gis_model


class BusinessVertical(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Business Vertical"
        verbose_name_plural = "Business Verticals"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Store(models.Model):
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
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    # FUTURE (GDAL / POSTGIS)
    # location = gis_models.PointField(geography=True)
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
    )
    is_open = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
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
