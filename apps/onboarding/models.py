import uuid
from django.db import models
from django.conf import settings


class ApplicationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft (Incomplete)"
    PENDING = "PENDING", "Pending Review"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    REQUEST_CHANGES = "REQUEST_CHANGES", "Changes Requested"


class MerchantApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant_applications")
    business_name = models.CharField(max_length=255)
    business_address = models.TextField()
    contact_number = models.CharField(max_length=15)
    dti_sec_certificate = models.FileField(upload_to="onboarding/merchants/dti_sec/")
    mayors_permit = models.FileField(upload_to="onboarding/merchants/mayors_permit/")
    bir_cor = models.FileField(upload_to="onboarding/merchants/bir_cor/", blank=True, null=True)
    halal_certification = models.FileField(upload_to="onboarding/merchants/halal/", blank=True, null=True)
    owner_valid_id = models.FileField(upload_to="onboarding/merchants/ids/")
    storefront_photo = models.ImageField(upload_to="onboarding/merchants/photos/")
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.DRAFT, db_index=True)
    admin_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Merchant Application"
        verbose_name_plural = "Merchant Applications"

    def __str__(self):
        return f"{self.business_name} ({self.status})"


class RiderApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rider_applications")
    vehicle_type = models.CharField(max_length=20, choices=[("MOTORCYCLE", "Motorcycle"), ("BICYCLE", "Bicycle")])
    plate_number = models.CharField(max_length=20, blank=True, null=True)
    professional_drivers_license = models.FileField(upload_to="onboarding/riders/license/")
    lto_or_cr = models.FileField(upload_to="onboarding/riders/or_cr/", blank=True, null=True)
    nbi_clearance = models.FileField(upload_to="onboarding/riders/nbi/")
    barangay_clearance = models.FileField(upload_to="onboarding/riders/barangay/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.DRAFT, db_index=True)
    admin_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Rider Application"
        verbose_name_plural = "Rider Applications"

    def __str__(self):
        return f"Rider: {self.applicant.username} ({self.status})"
