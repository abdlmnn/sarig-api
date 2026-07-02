from django.db import migrations


def normalize_required_documents(apps, schema_editor):
    BusinessVertical = apps.get_model("vendors", "BusinessVertical")
    BusinessVertical.objects.filter(slug="pharmacy").update(
        required_documents=["mayors_permit", "pharmacy_license"],
        requires_license=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0007_businessvertical_product_rules"),
    ]

    operations = [
        migrations.RunPython(normalize_required_documents, migrations.RunPython.noop),
    ]
