from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0003_public_signup_contract"),
    ]

    operations = [
        migrations.AlterField(
            model_name="merchantapplication",
            name="street",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
