from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0006_store_barangay_store_branch_name_store_company_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="business_hours",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="store",
            name="manual_override",
            field=models.CharField(
                blank=True,
                choices=[
                    ("OPEN_NOW", "Open now"),
                    ("CLOSED_MANUALLY", "Closed manually"),
                    ("CLOSED_TEMPORARILY", "Closed temporarily"),
                    ("PAUSED_ORDERS", "Paused orders"),
                ],
                max_length=30,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="manual_override_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
