import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_application_ids(apps, schema_editor):
    MerchantApplication = apps.get_model("onboarding", "MerchantApplication")
    RiderApplication = apps.get_model("onboarding", "RiderApplication")
    for prefix, model in (("MR", MerchantApplication), ("RD", RiderApplication)):
        for application in model.objects.all():
            while True:
                candidate = f"{prefix}-{uuid.uuid4().int % 9000 + 1000}"
                if not model.objects.filter(application_id=candidate).exists():
                    application.application_id = candidate
                    application.save(update_fields=["application_id"])
                    break


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0002_merchantapplication_barangay_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="merchantapplication",
            name="application_id",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="application_id",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.RunPython(backfill_application_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="merchantapplication",
            name="application_id",
            field=models.CharField(blank=True, db_index=True, max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="application_id",
            field=models.CharField(blank=True, db_index=True, max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="applicant",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="merchant_applications", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="applicant",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="rider_applications", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="contact_number",
            field=models.CharField(max_length=30),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="admin_remarks",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="barangay",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="branch_name",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="city",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="company_email",
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="owner_first_name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="owner_last_name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="postal_code",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="province",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="street",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="status",
            field=models.CharField(choices=[("DRAFT", "Draft (Incomplete)"), ("PENDING", "Pending Review"), ("UNDER_REVIEW", "Under Review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("REQUEST_CHANGES", "Changes Requested")], db_index=True, default="PENDING", max_length=20),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="admin_remarks",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="status",
            field=models.CharField(choices=[("DRAFT", "Draft (Incomplete)"), ("PENDING", "Pending Review"), ("UNDER_REVIEW", "Under Review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("REQUEST_CHANGES", "Changes Requested")], db_index=True, default="PENDING", max_length=20),
        ),
        migrations.AddField(
            model_name="merchantapplication",
            name="location_source",
            field=models.CharField(choices=[("manual", "Manual"), ("pin", "Pin")], default="manual", max_length=20),
        ),
        migrations.AddField(
            model_name="merchantapplication",
            name="requested_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="merchantapplication",
            name="terms_accepted",
            field=models.BooleanField(default=False),
        ),
        migrations.RemoveField(
            model_name="merchantapplication",
            name="halal_certification",
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="first_name",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="last_name",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="email",
            field=models.EmailField(default="", max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="phone_number",
            field=models.CharField(default="", max_length=30),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="terms_accepted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="current_address",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="barangay",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="city",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="province",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="postal_code",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="emergency_contact_name",
            field=models.CharField(default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="emergency_contact_number",
            field=models.CharField(default="", max_length=30),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="emergency_contact_relationship",
            field=models.CharField(default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="vehicle_brand",
            field=models.CharField(default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="vehicle_photo_front",
            field=models.ImageField(default="", upload_to="onboarding/riders/vehicles/front/"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="vehicle_photo_back",
            field=models.ImageField(default="", upload_to="onboarding/riders/vehicles/back/"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="riderapplication",
            name="requested_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="plate_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="vehicle_type",
            field=models.CharField(choices=[("MOTORCYCLE", "Motorcycle"), ("BICYCLE", "Bicycle"), ("CAR", "Car")], max_length=20),
        ),
        migrations.CreateModel(
            name="AccountSetupToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("application_id", models.CharField(db_index=True, max_length=20)),
                ("application_type", models.CharField(max_length=20)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ApplicationEditToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("application_id", models.CharField(db_index=True, max_length=20)),
                ("application_type", models.CharField(max_length=20)),
                ("requested_fields", models.JSONField(blank=True, default=list)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ApplicationStatusHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("application_id", models.CharField(db_index=True, max_length=20)),
                ("application_type", models.CharField(max_length=20)),
                ("from_status", models.CharField(blank=True, max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
