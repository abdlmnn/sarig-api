from django.db import migrations

from apps.operations.seed_data import MARAWI_SERVICE_ZONES


def seed_marawi_zones(apps, schema_editor):
    ServiceZone = apps.get_model("operations", "ServiceZone")
    for zone in MARAWI_SERVICE_ZONES:
        ServiceZone.objects.update_or_create(
            slug=zone["slug"],
            defaults={
                "name": zone["name"],
                "city": "Marawi",
                "province": "Lanao del Sur",
                "center_latitude": zone["center_latitude"],
                "center_longitude": zone["center_longitude"],
                "barangay_names": zone["barangay_names"],
                "priority": zone["priority"],
                "is_active": True,
            },
        )


def unseed_marawi_zones(apps, schema_editor):
    ServiceZone = apps.get_model("operations", "ServiceZone")
    ServiceZone.objects.filter(slug__in=[zone["slug"] for zone in MARAWI_SERVICE_ZONES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_marawi_zones, unseed_marawi_zones),
    ]
