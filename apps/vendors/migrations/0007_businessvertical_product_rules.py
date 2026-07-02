from django.db import migrations, models


VERTICALS = [
    {
        "name": "Restaurant",
        "slug": "restaurant",
        "allowed_product_types": ["food"],
        "requires_license": False,
        "required_documents": [],
    },
    {
        "name": "Pharmacy",
        "slug": "pharmacy",
        "allowed_product_types": ["medicine", "grocery", "general"],
        "requires_license": True,
        "required_documents": ["mayors_permit", "pharmacy_license"],
    },
    {
        "name": "Grocery",
        "slug": "grocery",
        "allowed_product_types": ["grocery", "general"],
        "requires_license": False,
        "required_documents": [],
    },
    {
        "name": "Market",
        "slug": "market",
        "allowed_product_types": ["food", "grocery", "general"],
        "requires_license": False,
        "required_documents": [],
    },
    {
        "name": "Convenience Store",
        "slug": "convenience-store",
        "allowed_product_types": ["grocery", "medicine", "general"],
        "requires_license": False,
        "required_documents": [],
    },
    {
        "name": "General Store",
        "slug": "general-store",
        "allowed_product_types": ["general", "grocery"],
        "requires_license": False,
        "required_documents": [],
    },
    {
        "name": "Bakery",
        "slug": "bakery",
        "allowed_product_types": ["food", "grocery"],
        "requires_license": False,
        "required_documents": [],
    },
]


def seed_verticals(apps, schema_editor):
    BusinessVertical = apps.get_model("vendors", "BusinessVertical")
    for vertical in VERTICALS:
        BusinessVertical.objects.update_or_create(
            slug=vertical["slug"],
            defaults={
                "name": vertical["name"],
                "allowed_product_types": vertical["allowed_product_types"],
                "requires_license": vertical["requires_license"],
                "required_documents": vertical["required_documents"],
                "is_active": True,
            },
        )

    BusinessVertical.objects.filter(slug="shop").update(
        allowed_product_types=["general", "grocery"],
        requires_license=False,
        required_documents=[],
    )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0006_store_barangay_store_branch_name_store_company_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessvertical",
            name="allowed_product_types",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="businessvertical",
            name="required_documents",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="businessvertical",
            name="requires_license",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(seed_verticals, migrations.RunPython.noop),
    ]
