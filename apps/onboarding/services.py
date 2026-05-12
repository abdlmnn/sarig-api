from django.db import transaction
from django.contrib.auth.models import Group
from .models import MerchantApplication, RiderApplication, ApplicationStatus
from apps.vendors.models import Store, BusinessVertical


class ApplicationService:
    @staticmethod
    @transaction.atomic
    def approve_merchant(application: MerchantApplication) -> Store:
        vertical, _ = BusinessVertical.objects.get_or_create(name="Restaurant")

        store = Store.objects.create(
            owner=application.applicant,
            vertical=vertical,
            name=application.business_name,
            address=application.business_address,
            contact_number=application.contact_number,
        )

        merchant_group, _ = Group.objects.get_or_create(name="Merchant")
        application.applicant.groups.add(merchant_group)

        application.status = ApplicationStatus.APPROVED
        application.save()

        return store

    @staticmethod
    @transaction.atomic
    def approve_rider(application: RiderApplication):
        rider_group, _ = Group.objects.get_or_create(name="Rider")
        application.applicant.groups.add(rider_group)

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
