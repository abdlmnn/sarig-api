from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

from .models import EmailTemplate


DEFAULT_TEMPLATES = {
    "onboarding.submitted": {
        "name": "Onboarding application submitted",
        "eyebrow": "Application received",
        "heading": "We have your application.",
        "subject": "We received your Sarig {{ application_type_label }} application",
        "body": (
            "Hi {{ applicant_name }},\n\n"
            "Thank you for applying to join Sarig as a {{ application_type_label }} partner. "
            "We received your application and it is now ready for our team to review.\n\n"
            "Application reference: {{ application_id }}\n"
            "Submitted on: {{ submitted_at }}\n\n"
            "We will review your information and documents, then email you when there is an update.\n\n"
            "Follow your application progress:\n{{ status_url }}\n\n"
            "Please keep your application reference for future inquiries."
        ),
        "html_body": (
            '<p style="margin:0 0 18px;color:#334155;font-size:15px;line-height:1.7;">'
            "Hi <strong style=\"color:#0f172a;\">{{ applicant_name }}</strong>,</p>"
            '<p style="margin:0 0 24px;color:#475569;font-size:15px;line-height:1.7;">'
            "Thank you for applying to join Sarig as a {{ application_type_label }} partner. "
            "We received your application and it is now ready for our team to review.</p>"
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="margin:0 0 24px;border:1px solid #e2e8f0;background:#f8fafc;">'
            '<tr><td style="padding:18px 20px;">'
            '<div style="color:#64748b;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">'
            "Application reference</div>"
            '<div style="margin-top:6px;color:#0f172a;font-size:18px;font-weight:800;letter-spacing:.3px;">'
            "{{ application_id }}</div>"
            '<div style="margin-top:8px;color:#64748b;font-size:12px;">Submitted {{ submitted_at }}</div>'
            "</td></tr></table>"
            '<div style="margin:0 0 26px;">'
            '<div style="margin-bottom:8px;color:#0f172a;font-size:13px;font-weight:800;">What happens next</div>'
            '<div style="color:#475569;font-size:14px;line-height:1.7;">'
            "Our onboarding team will review your information and documents. "
            "We will email you when your application is approved, needs changes, or has another update.</div>"
            "</div>"
            '<table role="presentation" cellspacing="0" cellpadding="0"><tr><td '
            'style="background:#8f1515;"><a href="{{ status_url }}" '
            'style="display:inline-block;padding:13px 20px;color:#ffffff;text-decoration:none;'
            'font-size:13px;font-weight:800;">View application status</a></td></tr></table>'
            '<p style="margin:22px 0 0;color:#64748b;font-size:12px;line-height:1.6;">'
            "Keep your application reference for future inquiries.</p>"
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


HTML_EMAIL_SHELL = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ subject }}</title>
</head>
<body style="margin:0;padding:0;background:#f4f1ee;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{{ subject }}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f1ee;">
    <tr>
      <td align="center" style="padding:32px 14px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="max-width:620px;background:#ffffff;border:1px solid #e7e2de;">
          <tr>
            <td style="padding:22px 28px;background:#0a0a0a;">
              <div style="color:#e5e1e1;font-size:24px;font-weight:800;letter-spacing:-.5px;">sarig<span style="color:#9a1414;">.</span></div>
              <div style="margin-top:3px;color:#a0a0a0;font-size:10px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;">
                Onboarding
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:34px 28px 30px;">
              <div style="margin-bottom:10px;color:#8f1515;font-size:11px;font-weight:800;letter-spacing:1.6px;text-transform:uppercase;">
                {{ eyebrow }}
              </div>
              <h1 style="margin:0 0 24px;color:#0f172a;font-family:Arial,Helvetica,sans-serif;font-size:24px;font-weight:700;line-height:1.35;letter-spacing:0;">
                {{ heading }}
              </h1>
              {{ content|safe }}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px;border-top:1px solid #e2e8f0;background:#fafafa;">
              <p style="margin:0;color:#64748b;font-size:11px;line-height:1.6;">
                This is an automated message from Sarig. Please do not send passwords or sensitive documents by email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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
    subject = render_text(payload["subject"], context)
    message = render_text(payload["body"], context)
    html_body = payload.get("html_body")
    if html_body:
        content = render_text(html_body, context)
    else:
        content = linebreaks(escape(message))
    html_message = render_text(
        HTML_EMAIL_SHELL,
        {
            "subject": subject,
            "content": mark_safe(content),
            "eyebrow": payload.get("eyebrow", "Sarig notification"),
            "heading": payload.get("heading", subject),
        },
    )
    return {"subject": subject, "message": message, "html_message": html_message}


def send_templated_email(key, recipient, context, *, fail_silently=True):
    if not recipient:
        return False

    email = render_email(key, context)
    try:
        return send_mail(
            email["subject"],
            email["message"],
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sarig.local"),
            [recipient],
            fail_silently=fail_silently,
            html_message=email["html_message"],
        ) > 0
    except Exception:
        if not fail_silently:
            raise
        return False
