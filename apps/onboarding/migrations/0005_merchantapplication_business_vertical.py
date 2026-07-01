import django.db.models.deletion
from django.db import migrations, models


def backfill_business_vertical(apps, schema_editor):
    MerchantApplication = apps.get_model("onboarding", "MerchantApplication")
    BusinessVertical = apps.get_model("vendors", "BusinessVertical")

    restaurant = BusinessVertical.objects.filter(slug="restaurant").first()
    general_store = BusinessVertical.objects.filter(slug="general-store").first()

    for application in MerchantApplication.objects.filter(business_vertical__isnull=True):
        if application.business_type == "RESTAURANT" and restaurant:
            application.business_vertical = restaurant
        elif general_store:
            application.business_vertical = general_store
        application.save(update_fields=["business_vertical"])


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0007_businessvertical_product_rules"),
        ("onboarding", "0004_make_merchant_street_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchantapplication",
            name="business_vertical",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merchant_applications", to="vendors.businessvertical"),
        ),
        migrations.RunPython(backfill_business_vertical, migrations.RunPython.noop),
    ]
