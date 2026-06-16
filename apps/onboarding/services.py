from django.db import transaction
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import MerchantApplication, RiderApplication, ApplicationStatus
from apps.users.models import Role
from apps.vendors.models import Store, BusinessVertical


class ApplicationService:
    @staticmethod
    @transaction.atomic
    def approve_merchant(application: MerchantApplication) -> Store:
        required_fields = {
            "business_address": application.business_address,
            "city": application.city,
            "latitude": application.latitude,
            "longitude": application.longitude,
        }
        missing_fields = [field for field, value in required_fields.items() if value in (None, "")]
        if missing_fields:
            raise ValidationError(f"Merchant application is missing required store fields: {', '.join(missing_fields)}.")

        vertical_name = application.get_business_type_display()
        vertical, _ = BusinessVertical.objects.get_or_create(
            slug=slugify(vertical_name),
            defaults={"name": vertical_name},
        )

        store = Store.objects.create(
            owner=application.applicant,
            vertical=vertical,
            name=application.business_name,
            branch_name=application.branch_name,
            company_email=application.company_email,
            contact_number=application.contact_number,
            delivery_time=application.delivery_time,
            latitude=application.latitude,
            longitude=application.longitude,
            street_address=application.pinned_address or application.business_address,
            city=application.city,
            barangay=application.barangay,
            province=application.province,
            postal_code=application.postal_code,
            pinned_address=application.pinned_address,
            image=application.storefront_photo,
        )

        merchant_group, _ = Group.objects.get_or_create(name="Merchant")
        application.applicant.groups.add(merchant_group)
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        application.applicant.roles.add(merchant_role)

        application.status = ApplicationStatus.APPROVED
        application.save()

        return store

    @staticmethod
    @transaction.atomic
    def approve_rider(application: RiderApplication):
        rider_group, _ = Group.objects.get_or_create(name="Rider")
        application.applicant.groups.add(rider_group)
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        application.applicant.roles.add(rider_role)

        application.status = ApplicationStatus.APPROVED
        application.save()

    @staticmethod
    def reject_application(application, remarks: str):
        application.status = ApplicationStatus.REJECTED
        application.admin_remarks = remarks
        application.save()

    @staticmethod
    def request_changes(application, remarks: str):
        application.status = ApplicationStatus.REQUEST_CHANGES
        application.admin_remarks = remarks
        application.save()
