import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class LoadStatus(models.TextChoices):
    STABLE = "STABLE", "Stable"
    HIGH = "HIGH", "High"
    WATCH = "WATCH", "Watch"


class AssignmentEntityType(models.TextChoices):
    STORE = "STORE", "Store"
    RIDER = "RIDER", "Rider"
    ORDER = "ORDER", "Order"
    RIDE = "RIDE", "Ride"


class AssignmentSource(models.TextChoices):
    AUTO = "AUTO", "Auto"
    MANUAL = "MANUAL", "Manual"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class ServiceZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    city = models.CharField(max_length=100, default="Marawi")
    province = models.CharField(max_length=100, default="Lanao del Sur")
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    boundary = models.JSONField(default=dict, blank=True)
    barangay_names = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["city", "is_active"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"


class ServiceZoneMetricSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ServiceZone, on_delete=models.CASCADE, related_name="metric_snapshots")
    active_orders = models.PositiveIntegerField(default=0)
    active_transport_bookings = models.PositiveIntegerField(default=0)
    available_riders = models.PositiveIntegerField(default=0)
    active_riders = models.PositiveIntegerField(default=0)
    approved_merchants = models.PositiveIntegerField(default=0)
    average_delay_minutes = models.PositiveIntegerField(default=0)
    load_status = models.CharField(max_length=20, choices=LoadStatus.choices, default=LoadStatus.STABLE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["zone", "-created_at"]),
            models.Index(fields=["load_status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.zone.name} metrics at {self.created_at}"


class ServiceZoneAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ServiceZone, on_delete=models.CASCADE, related_name="assignments")
    entity_type = models.CharField(max_length=20, choices=AssignmentEntityType.choices)
    entity_id = models.UUIDField(db_index=True)
    source = models.CharField(max_length=20, choices=AssignmentSource.choices, default=AssignmentSource.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("entity_type", "entity_id")]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["zone", "entity_type"]),
        ]

    def __str__(self):
        return f"{self.entity_type} {self.entity_id} -> {self.zone.name}"


class AdminAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices, default=AlertSeverity.INFO, db_index=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    source = models.CharField(max_length=80, default="operations", db_index=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_admin_alerts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["severity", "is_resolved"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def mark_resolved(self, user):
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=["is_resolved", "resolved_by", "resolved_at"])

    def __str__(self):
        return f"{self.get_severity_display()}: {self.title}"
