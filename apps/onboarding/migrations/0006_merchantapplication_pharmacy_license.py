from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0005_merchantapplication_business_vertical"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchantapplication",
            name="pharmacy_license",
            field=models.FileField(blank=True, null=True, upload_to="onboarding/merchants/pharmacy_license/"),
        ),
    ]
