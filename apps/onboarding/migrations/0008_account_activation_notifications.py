import uuid

from django.db import migrations, models
from django.utils import timezone


def activate_provisioned_applications(apps, schema_editor):
    MerchantApplication = apps.get_model("onboarding", "MerchantApplication")
    RiderApplication = apps.get_model("onboarding", "RiderApplication")
    AccountSetupToken = apps.get_model("onboarding", "AccountSetupToken")
    Store = apps.get_model("vendors", "Store")
    RiderProfile = apps.get_model("riders", "RiderProfile")

    merchant_user_ids = Store.objects.values_list("owner_id", flat=True)
    rider_user_ids = RiderProfile.objects.values_list("user_id", flat=True)
    merchant_ids = list(
        MerchantApplication.objects.filter(
            status="APPROVED",
            applicant_id__in=merchant_user_ids,
            applicant__is_active=True,
        ).values_list("application_id", flat=True)
    )
    rider_ids = list(
        RiderApplication.objects.filter(
            status="APPROVED",
            applicant_id__in=rider_user_ids,
            applicant__is_active=True,
        ).values_list("application_id", flat=True)
    )
    MerchantApplication.objects.filter(application_id__in=merchant_ids).update(status="ACTIVE")
    RiderApplication.objects.filter(application_id__in=rider_ids).update(status="ACTIVE")
    AccountSetupToken.objects.filter(
        application_id__in=merchant_ids + rider_ids,
        used_at__isnull=True,
    ).update(used_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0007_extend_application_id_length"),
        ("riders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="merchantapplication",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft (Incomplete)"),
                    ("PENDING", "Pending Review"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("REQUEST_CHANGES", "Changes Requested"),
                    ("ACTIVE", "Active"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft (Incomplete)"),
                    ("PENDING", "Pending Review"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("REQUEST_CHANGES", "Changes Requested"),
                    ("ACTIVE", "Active"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="accountsetuptoken",
            name="token",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="accountsetuptoken",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(activate_provisioned_applications, migrations.RunPython.noop),
        migrations.CreateModel(
            name="OnboardingNotificationDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("APPLICATION_SUBMITTED", "Application Submitted"),
                            ("MERCHANT_APPROVED", "Merchant Approved"),
                            ("RIDER_APPROVED", "Rider Approved"),
                            ("APPLICATION_REJECTED", "Application Rejected"),
                            ("CHANGES_REQUESTED", "Changes Requested"),
                            ("ACCOUNT_ACTIVATED", "Account Activated"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("EMAIL", "Email"), ("SMS", "SMS"), ("IN_APP", "In App")],
                        max_length=20,
                    ),
                ),
                ("application_id", models.CharField(db_index=True, max_length=40)),
                ("application_type", models.CharField(max_length=20)),
                ("recipient", models.CharField(max_length=320)),
                ("template_key", models.CharField(blank=True, max_length=100)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("idempotency_key", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                            ("SKIPPED", "Skipped"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("next_attempt_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="onboardingnotificationdelivery",
            index=models.Index(fields=["application_id", "event"], name="onboarding__applica_78e3b9_idx"),
        ),
    ]
