import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApplicationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft (Incomplete)"
    PENDING = "PENDING", "Pending Review"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    REQUEST_CHANGES = "REQUEST_CHANGES", "Changes Requested"


class BusinessType(models.TextChoices):
    SHOP = "SHOP", "Shop"
    RESTAURANT = "RESTAURANT", "Restaurant"


class DeliveryTime(models.TextChoices):
    MORNING = "MORNING", "Morning"
    AFTERNOON = "AFTERNOON", "Afternoon"
    EVENING = "EVENING", "Evening"
    ALL_DAY = "ALL_DAY", "All day"


class LocationSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    PIN = "pin", "Pin"


class VehicleType(models.TextChoices):
    MOTORCYCLE = "MOTORCYCLE", "Motorcycle"
    BICYCLE = "BICYCLE", "Bicycle"
    CAR = "CAR", "Car"


def generate_application_id(prefix, model):
    while True:
        candidate = f"{prefix}-{uuid.uuid4().int % 9000 + 1000}"
        if not model.objects.filter(application_id=candidate).exists():
            return candidate


class MerchantApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_id = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="merchant_applications",
        null=True,
        blank=True,
    )
    business_name = models.CharField(max_length=255)
    owner_first_name = models.CharField(max_length=100)
    owner_last_name = models.CharField(max_length=100)
    company_email = models.EmailField()
    contact_number = models.CharField(max_length=30)
    business_type = models.CharField(max_length=20, choices=BusinessType.choices, default=BusinessType.RESTAURANT)
    delivery_time = models.CharField(max_length=20, choices=DeliveryTime.choices, default=DeliveryTime.ALL_DAY)
    branch_name = models.CharField(max_length=120)
    terms_accepted = models.BooleanField(default=False)
    business_address = models.TextField()
    city = models.CharField(max_length=100)
    barangay = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    street = models.CharField(max_length=255)
    location_source = models.CharField(max_length=20, choices=LocationSource.choices, default=LocationSource.MANUAL)
    pinned_address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    dti_sec_certificate = models.FileField(upload_to="onboarding/merchants/dti_sec/")
    mayors_permit = models.FileField(upload_to="onboarding/merchants/mayors_permit/")
    bir_cor = models.FileField(upload_to="onboarding/merchants/bir_cor/", blank=True, null=True)
    owner_valid_id = models.FileField(upload_to="onboarding/merchants/ids/")
    storefront_photo = models.ImageField(upload_to="onboarding/merchants/photos/")
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING, db_index=True)
    admin_remarks = models.TextField(blank=True)
    requested_fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Merchant Application"
        verbose_name_plural = "Merchant Applications"

    @property
    def applicant_name(self):
        return f"{self.owner_first_name} {self.owner_last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = generate_application_id("MR", MerchantApplication)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_id} - {self.business_name} ({self.status})"


class RiderApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_id = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rider_applications",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30)
    terms_accepted = models.BooleanField(default=False)
    current_address = models.TextField()
    barangay = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    emergency_contact_name = models.CharField(max_length=150)
    emergency_contact_number = models.CharField(max_length=30)
    emergency_contact_relationship = models.CharField(max_length=80)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    vehicle_brand = models.CharField(max_length=120)
    plate_number = models.CharField(max_length=20, blank=True)
    vehicle_photo_front = models.ImageField(upload_to="onboarding/riders/vehicles/front/")
    vehicle_photo_back = models.ImageField(upload_to="onboarding/riders/vehicles/back/")
    professional_drivers_license = models.FileField(upload_to="onboarding/riders/license/")
    lto_or_cr = models.FileField(upload_to="onboarding/riders/or_cr/", blank=True, null=True)
    nbi_clearance = models.FileField(upload_to="onboarding/riders/nbi/")
    barangay_clearance = models.FileField(upload_to="onboarding/riders/barangay/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING, db_index=True)
    admin_remarks = models.TextField(blank=True)
    requested_fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Rider Application"
        verbose_name_plural = "Rider Applications"

    @property
    def applicant_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = generate_application_id("RD", RiderApplication)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_id} - {self.applicant_name} ({self.status})"


class ApplicationStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_id = models.CharField(max_length=20, db_index=True)
    application_type = models.CharField(max_length=20)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ApplicationEditToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    application_id = models.CharField(max_length=20, db_index=True)
    application_type = models.CharField(max_length=20)
    requested_fields = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class AccountSetupToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    application_id = models.CharField(max_length=20, db_index=True)
    application_type = models.CharField(max_length=20)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
