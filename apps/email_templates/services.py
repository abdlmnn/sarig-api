from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template

from .models import EmailTemplate


DEFAULT_TEMPLATES = {
    "onboarding.submitted": {
        "name": "Onboarding application submitted",
        "subject": "Sarig application received",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Your {{ application_type_label }} application was submitted.\n\n"
            "Application ID: {{ application_id }}\n"
            "Status check: {{ status_url }}\n"
            "Submitted: {{ submitted_at }}\n\n"
            "We will notify you when there is an update."
        ),
    },
    "onboarding.approved.merchant": {
        "name": "Merchant application approved",
        "subject": "Sarig merchant application approved",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Your merchant application {{ application_id }} was approved.\n\n"
            "Set up your merchant account here:\n{{ setup_url }}\n\n"
            "This link expires in 7 days."
        ),
    },
    "onboarding.approved.rider": {
        "name": "Rider application approved",
        "subject": "Sarig rider application approved",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Your rider application {{ application_id }} was approved.\n\n"
            "Set up your rider account here:\n{{ setup_url }}\n\n"
            "This link expires in 7 days."
        ),
    },
    "onboarding.request_changes": {
        "name": "Onboarding changes requested",
        "subject": "Sarig application changes requested",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Please update your application {{ application_id }}.\n\n"
            "Admin remarks:\n{{ remarks }}\n\n"
            "Requested fields: {{ requested_fields }}\n\n"
            "Edit your application here:\n{{ edit_url }}\n\n"
            "This link expires in 7 days."
        ),
    },
    "onboarding.rejected": {
        "name": "Onboarding application rejected",
        "subject": "Sarig application rejected",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Your application {{ application_id }} was rejected.\n\n"
            "Reason:\n{{ remarks }}\n\n"
            "If you believe this is a mistake, contact Sarig support."
        ),
    },
    "onboarding.account_setup_completed": {
        "name": "Account setup completed",
        "subject": "Sarig account setup completed",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Your Sarig account setup is complete. You can now sign in."
        ),
    },
}


def render_text(value, context):
    return Template(value).render(Context(context))


def get_template_payload(key):
    template = EmailTemplate.objects.filter(key=key, is_active=True).first()
    if template:
        return {"subject": template.subject, "body": template.body}

    default = DEFAULT_TEMPLATES.get(key)
    if not default:
        raise ValueError(f"Unknown email template key: {key}")
    return default


def render_email(key, context):
    payload = get_template_payload(key)
    return {
        "subject": render_text(payload["subject"], context),
        "message": render_text(payload["body"], context),
    }


def send_templated_email(key, recipient, context):
    if not recipient:
        return False

    email = render_email(key, context)
    try:
        return send_mail(
            email["subject"],
            email["message"],
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sarig.local"),
            [recipient],
            fail_silently=True,
        ) > 0
    except Exception:
        return False
