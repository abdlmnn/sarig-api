from datetime import timedelta
from secrets import token_hex

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.riders.models import RiderProfile
from apps.users.models import Role
from apps.vendors.models import BusinessVertical, Store

from .models import (
    AccountSetupToken,
    ApplicationEditToken,
    ApplicationStatus,
    ApplicationStatusHistory,
    MerchantApplication,
    NotificationEvent,
    RiderApplication,
)
from .notifications import applicant_email, application_type, queue_onboarding_event


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


def record_history(application, to_status, actor=None, remarks=""):
    return ApplicationStatusHistory.objects.create(
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
        ApplicationStatusHistory.objects.get_or_create(
            application_id=application.application_id,
            application_type=application_type(application),
            from_status="",
            to_status=ApplicationStatus.PENDING,
            defaults={"remarks": "Application submitted."},
        )
        deliveries = queue_onboarding_event(
            application,
            NotificationEvent.APPLICATION_SUBMITTED,
            application.pk,
            {"submitted_at": application.created_at.strftime("%Y-%m-%d %H:%M")},
        )
        return bool(deliveries)

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
        AccountSetupToken.objects.filter(
            application_id=application.application_id,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        return AccountSetupToken.objects.create(
            application_id=application.application_id,
            application_type=application_type(application),
            expires_at=timezone.now() + timedelta(days=7),
        )

    @staticmethod
    def _locked(application):
        return type(application).objects.select_for_update().get(pk=application.pk)

    @staticmethod
    def _require_reviewable(application):
        if application.status not in (ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW):
            raise ValidationError(f"Application cannot be reviewed while its status is {application.status}.")

    @staticmethod
    @transaction.atomic
    def approve_merchant(application: MerchantApplication, actor=None):
        application = ApplicationService._locked(application)
        if application.status == ApplicationStatus.APPROVED:
            invitation = AccountSetupToken.objects.filter(
                application_id=application.application_id,
                used_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if invitation:
                return invitation
        ApplicationService._require_reviewable(application)
        ApplicationService.validate_merchant_ready_for_approval(application)
        record_history(application, ApplicationStatus.APPROVED, actor=actor)
        application.status = ApplicationStatus.APPROVED
        application.save(update_fields=["status", "updated_at"])
        ApplicationEditToken.objects.filter(
            application_id=application.application_id,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        setup_token = ApplicationService.create_setup_token(application)
        queue_onboarding_event(
            application,
            NotificationEvent.MERCHANT_APPROVED,
            setup_token.pk,
            {"setup_invitation_id": str(setup_token.pk)},
        )
        return setup_token

    @staticmethod
    @transaction.atomic
    def approve_rider(application: RiderApplication, actor=None):
        application = ApplicationService._locked(application)
        if application.status == ApplicationStatus.APPROVED:
            invitation = AccountSetupToken.objects.filter(
                application_id=application.application_id,
                used_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if invitation:
                return invitation
        ApplicationService._require_reviewable(application)
        record_history(application, ApplicationStatus.APPROVED, actor=actor)
        application.status = ApplicationStatus.APPROVED
        application.save(update_fields=["status", "updated_at"])
        ApplicationEditToken.objects.filter(
            application_id=application.application_id,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        setup_token = ApplicationService.create_setup_token(application)
        queue_onboarding_event(
            application,
            NotificationEvent.RIDER_APPROVED,
            setup_token.pk,
            {"setup_invitation_id": str(setup_token.pk)},
        )
        return setup_token

    @staticmethod
    @transaction.atomic
    def reissue_setup_invitation(application, actor=None):
        application = ApplicationService._locked(application)
        if application.status != ApplicationStatus.APPROVED:
            raise ValidationError("Only approved applications awaiting account setup can receive a new invitation.")
        if application.applicant_id and application.applicant.is_active:
            raise ValidationError("This application is already linked to an active account.")
        setup_token = ApplicationService.create_setup_token(application)
        event = NotificationEvent.MERCHANT_APPROVED if isinstance(application, MerchantApplication) else NotificationEvent.RIDER_APPROVED
        queue_onboarding_event(
            application,
            event,
            setup_token.pk,
            {"setup_invitation_id": str(setup_token.pk), "reissued": True},
        )
        return setup_token

    @staticmethod
    @transaction.atomic
    def reissue_change_request(application, actor=None):
        application = ApplicationService._locked(application)
        if application.status != ApplicationStatus.REQUEST_CHANGES:
            raise ValidationError("Only applications awaiting changes can receive a new edit invitation.")
        ApplicationEditToken.objects.filter(
            application_id=application.application_id,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        edit_token = ApplicationService.create_edit_token(application, application.requested_fields)
        queue_onboarding_event(
            application,
            NotificationEvent.CHANGES_REQUESTED,
            edit_token.pk,
            {
                "edit_token_id": str(edit_token.pk),
                "remarks": application.admin_remarks,
                "requested_fields": application.requested_fields,
                "reissued": True,
            },
        )
        return edit_token

    @staticmethod
    def validate_merchant_ready_for_approval(application):
        required_fields = {
            "business_address": application.business_address,
            "city": application.city,
            "latitude": application.latitude,
            "longitude": application.longitude,
        }
        missing_fields = [field for field, value in required_fields.items() if value in (None, "")]
        if missing_fields:
            raise ValidationError(f"Merchant application is missing required store fields: {', '.join(missing_fields)}.")

    @staticmethod
    def create_store_for_merchant(application: MerchantApplication) -> Store:
        ApplicationService.validate_merchant_ready_for_approval(application)

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
        application = ApplicationService._locked(application)
        if application.status == ApplicationStatus.REJECTED:
            return application
        if application.status not in (
            ApplicationStatus.PENDING,
            ApplicationStatus.UNDER_REVIEW,
            ApplicationStatus.REQUEST_CHANGES,
        ):
            raise ValidationError(f"Application cannot be rejected while its status is {application.status}.")
        history = record_history(application, ApplicationStatus.REJECTED, actor=actor, remarks=remarks)
        application.status = ApplicationStatus.REJECTED
        application.admin_remarks = remarks
        application.save(update_fields=["status", "admin_remarks", "updated_at"])
        now = timezone.now()
        ApplicationEditToken.objects.filter(application_id=application.application_id, revoked_at__isnull=True).update(revoked_at=now)
        AccountSetupToken.objects.filter(
            application_id=application.application_id,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=now)
        queue_onboarding_event(
            application,
            NotificationEvent.APPLICATION_REJECTED,
            history.pk,
            {"remarks": remarks},
        )
        return application

    @staticmethod
    @transaction.atomic
    def request_changes(application, remarks: str, requested_fields=None, actor=None):
        application = ApplicationService._locked(application)
        ApplicationService._require_reviewable(application)
        requested_fields = requested_fields or []
        record_history(application, ApplicationStatus.REQUEST_CHANGES, actor=actor, remarks=remarks)
        application.status = ApplicationStatus.REQUEST_CHANGES
        application.admin_remarks = remarks
        application.requested_fields = requested_fields
        application.save(update_fields=["status", "admin_remarks", "requested_fields", "updated_at"])
        ApplicationEditToken.objects.filter(
            application_id=application.application_id,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        edit_token = ApplicationService.create_edit_token(application, requested_fields)
        queue_onboarding_event(
            application,
            NotificationEvent.CHANGES_REQUESTED,
            edit_token.pk,
            {
                "edit_token_id": str(edit_token.pk),
                "remarks": remarks,
                "requested_fields": requested_fields,
            },
        )
        return edit_token

    @staticmethod
    @transaction.atomic
    def complete_account_setup(setup_token: AccountSetupToken, password: str):
        application = get_application(setup_token.application_id)
        application = ApplicationService._locked(application)
        setup_token = AccountSetupToken.objects.select_for_update().get(pk=setup_token.pk)
        if setup_token.application_id != application.application_id or not setup_token.is_active:
            raise ValidationError("Account setup token is expired or already used.")
        if application.status != ApplicationStatus.APPROVED:
            raise ValidationError("Application must be approved before account setup.")

        email = applicant_email(application).strip().lower()
        validate_password(password)
        user_model = get_user_model()
        phone = compact_phone(application.contact_number if isinstance(application, MerchantApplication) else application.phone_number) or None
        user = None
        if application.applicant_id:
            candidate = user_model.objects.select_for_update().get(pk=application.applicant_id)
            if candidate.is_active or candidate.email.lower() != email:
                raise ValidationError("The linked account cannot be configured with this invitation. Contact support.")
            user = candidate
        elif user_model.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Contact support to link the application.")

        if phone and user_model.objects.filter(phone_number=phone).exclude(pk=getattr(user, "pk", None)).exists():
            raise ValidationError("An account with this phone number already exists.")

        first_name = application.owner_first_name if isinstance(application, MerchantApplication) else application.first_name
        last_name = application.owner_last_name if isinstance(application, MerchantApplication) else application.last_name
        if user is None:
            user = user_model.objects.create_user(
                username=ApplicationService.generate_internal_username(email),
                email=email,
                password=password,
                phone_number=phone,
                first_name=first_name,
                last_name=last_name,
                is_active=False,
            )
        else:
            user.set_password(password)
            user.first_name = first_name
            user.last_name = last_name
            user.phone_number = phone
        user.is_active = True
        user.save()
        application.applicant = user

        if isinstance(application, MerchantApplication):
            ApplicationService.assign_role(user, "Merchant")
            ApplicationService.create_store_for_merchant(application)
        else:
            ApplicationService.assign_role(user, "Rider")
            RiderProfile.objects.get_or_create(
                user=user,
                defaults={
                    "vehicle_type": application.vehicle_type,
                    "plate_number": application.plate_number,
                },
            )

        record_history(application, ApplicationStatus.ACTIVE)
        application.status = ApplicationStatus.ACTIVE
        application.admin_remarks = ""
        application.requested_fields = []
        application.save(update_fields=["applicant", "status", "admin_remarks", "requested_fields", "updated_at"])
        now = timezone.now()
        AccountSetupToken.objects.filter(pk=setup_token.pk).update(used_at=now)
        AccountSetupToken.objects.filter(
            application_id=application.application_id,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=now)
        queue_onboarding_event(
            application,
            NotificationEvent.ACCOUNT_ACTIVATED,
            setup_token.pk,
        )
        return user

    @staticmethod
    def generate_internal_username(email):
        base = slugify(email.split("@", 1)[0])[:120] or "merchant"
        user_model = get_user_model()
        while True:
            candidate = f"{base}-{token_hex(4)}"
            if not user_model.objects.filter(username__iexact=candidate).exists():
                return candidate
