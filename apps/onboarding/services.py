from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.email_templates.services import send_templated_email
from apps.riders.models import RiderProfile
from apps.users.models import Role
from apps.vendors.models import BusinessVertical, Store

from .models import (
    AccountSetupToken,
    ApplicationEditToken,
    ApplicationStatus,
    ApplicationStatusHistory,
    MerchantApplication,
    RiderApplication,
)


FRONTEND_BASE_URL = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")


def compact_phone(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("63"):
        digits = f"+{digits}"
    elif digits.startswith("0"):
        digits = f"+63{digits[1:]}"
    elif digits:
        digits = f"+{digits}"
    return digits[:15]


def get_application(application_id):
    if application_id.startswith("MR-"):
        return MerchantApplication.objects.get(application_id=application_id)
    if application_id.startswith("RD-"):
        return RiderApplication.objects.get(application_id=application_id)
    raise ValidationError("Unknown application id.")


def application_type(application):
    return "MERCHANT" if isinstance(application, MerchantApplication) else "RIDER"


def applicant_email(application):
    return application.company_email if isinstance(application, MerchantApplication) else application.email


def applicant_name(application):
    return application.applicant_name or applicant_email(application)


def email_context(application, **extra):
    context = {
        "application_id": application.application_id,
        "application_type": application_type(application),
        "application_type_label": application_type(application).lower(),
        "applicant_name": applicant_name(application),
    }
    context.update(extra)
    return context


def record_history(application, to_status, actor=None, remarks=""):
    ApplicationStatusHistory.objects.create(
        application_id=application.application_id,
        application_type=application_type(application),
        from_status=application.status,
        to_status=to_status,
        actor=actor,
        remarks=remarks or "",
    )


class ApplicationService:
    @staticmethod
    def send_submission_confirmation(application):
        app_type = application_type(application).lower()
        status_url = f"{FRONTEND_BASE_URL}/{app_type}/status"
        return send_templated_email(
            "onboarding.submitted",
            applicant_email(application),
            email_context(
                application,
                status_url=status_url,
                submitted_at=application.created_at.strftime("%Y-%m-%d %H:%M"),
            ),
        )

    @staticmethod
    def create_edit_token(application, requested_fields):
        return ApplicationEditToken.objects.create(
            application_id=application.application_id,
            application_type=application_type(application),
            requested_fields=requested_fields,
            expires_at=timezone.now() + timedelta(days=7),
        )

    @staticmethod
    def create_setup_token(application):
        return AccountSetupToken.objects.create(
            application_id=application.application_id,
            application_type=application_type(application),
            expires_at=timezone.now() + timedelta(days=7),
        )

    @staticmethod
    @transaction.atomic
    def approve_merchant(application: MerchantApplication, actor=None):
        record_history(application, ApplicationStatus.APPROVED, actor=actor)
        application.status = ApplicationStatus.APPROVED
        application.save(update_fields=["status", "updated_at"])
        setup_token = ApplicationService.create_setup_token(application)

        store = None
        if application.applicant_id:
            store = ApplicationService.create_store_for_merchant(application)
            ApplicationService.assign_role(application.applicant, "Merchant")

        setup_url = f"{FRONTEND_BASE_URL}/accounts/setup/{setup_token.token}"
        send_templated_email(
            "onboarding.approved.merchant",
            applicant_email(application),
            email_context(application, setup_url=setup_url),
        )
        return store or setup_token

    @staticmethod
    @transaction.atomic
    def approve_rider(application: RiderApplication, actor=None):
        record_history(application, ApplicationStatus.APPROVED, actor=actor)
        application.status = ApplicationStatus.APPROVED
        application.save(update_fields=["status", "updated_at"])
        setup_token = ApplicationService.create_setup_token(application)

        if application.applicant_id:
            ApplicationService.assign_role(application.applicant, "Rider")
            RiderProfile.objects.get_or_create(
                user=application.applicant,
                defaults={
                    "vehicle_type": application.vehicle_type,
                    "plate_number": application.plate_number,
                },
            )

        setup_url = f"{FRONTEND_BASE_URL}/accounts/setup/{setup_token.token}"
        send_templated_email(
            "onboarding.approved.rider",
            applicant_email(application),
            email_context(application, setup_url=setup_url),
        )
        return setup_token

    @staticmethod
    def create_store_for_merchant(application: MerchantApplication) -> Store:
        required_fields = {
            "business_address": application.business_address,
            "city": application.city,
            "latitude": application.latitude,
            "longitude": application.longitude,
        }
        missing_fields = [field for field, value in required_fields.items() if value in (None, "")]
        if missing_fields:
            raise ValidationError(f"Merchant application is missing required store fields: {', '.join(missing_fields)}.")

        vertical = application.business_vertical
        if vertical is None:
            vertical_name = application.get_business_type_display()
            vertical, _ = BusinessVertical.objects.get_or_create(
                slug=slugify(vertical_name),
                defaults={"name": vertical_name},
            )

        return Store.objects.create(
            owner=application.applicant,
            vertical=vertical,
            name=application.business_name,
            branch_name=application.branch_name,
            company_email=application.company_email,
            contact_number=compact_phone(application.contact_number),
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

    @staticmethod
    def assign_role(user, role_name):
        group, _ = Group.objects.get_or_create(name=role_name)
        user.groups.add(group)
        role, _ = Role.objects.get_or_create(name=role_name)
        user.roles.add(role)

    @staticmethod
    @transaction.atomic
    def reject_application(application, remarks: str, actor=None):
        record_history(application, ApplicationStatus.REJECTED, actor=actor, remarks=remarks)
        application.status = ApplicationStatus.REJECTED
        application.admin_remarks = remarks
        application.save(update_fields=["status", "admin_remarks", "updated_at"])
        send_templated_email(
            "onboarding.rejected",
            applicant_email(application),
            email_context(application, remarks=remarks),
        )

    @staticmethod
    @transaction.atomic
    def request_changes(application, remarks: str, requested_fields=None, actor=None):
        requested_fields = requested_fields or []
        record_history(application, ApplicationStatus.REQUEST_CHANGES, actor=actor, remarks=remarks)
        application.status = ApplicationStatus.REQUEST_CHANGES
        application.admin_remarks = remarks
        application.requested_fields = requested_fields
        application.save(update_fields=["status", "admin_remarks", "requested_fields", "updated_at"])
        edit_token = ApplicationService.create_edit_token(application, requested_fields)
        app_type = application_type(application).lower()
        edit_url = f"{FRONTEND_BASE_URL}/{app_type}/application/edit/{edit_token.token}"
        send_templated_email(
            "onboarding.request_changes",
            applicant_email(application),
            email_context(
                application,
                edit_url=edit_url,
                remarks=remarks,
                requested_fields=", ".join(requested_fields) if requested_fields else "None",
            ),
        )
        return edit_token

    @staticmethod
    @transaction.atomic
    def complete_account_setup(setup_token: AccountSetupToken, username: str, password: str):
        if not setup_token.is_active:
            raise ValidationError("Account setup token is expired or already used.")

        application = get_application(setup_token.application_id)
        if application.status != ApplicationStatus.APPROVED:
            raise ValidationError("Application must be approved before account setup.")

        email = applicant_email(application)
        user = get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            phone_number=compact_phone(application.contact_number if isinstance(application, MerchantApplication) else application.phone_number),
        )
        application.applicant = user
        application.save(update_fields=["applicant", "updated_at"])

        if isinstance(application, MerchantApplication):
            ApplicationService.assign_role(user, "Merchant")
            ApplicationService.create_store_for_merchant(application)
        else:
            ApplicationService.assign_role(user, "Rider")
            RiderProfile.objects.create(
                user=user,
                vehicle_type=application.vehicle_type,
                plate_number=application.plate_number,
            )

        setup_token.mark_used()
        send_templated_email(
            "onboarding.account_setup_completed",
            email,
            email_context(application),
        )
        return user
