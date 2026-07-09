from django.core.management.base import BaseCommand

from apps.operations.models import ServiceZone
from apps.operations.seed_data import MARAWI_SERVICE_ZONES


class Command(BaseCommand):
    help = "Seed or update Marawi service zones for admin operations."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for zone in MARAWI_SERVICE_ZONES:
            _, was_created = ServiceZone.objects.update_or_create(
                slug=zone["slug"],
                defaults={
                    "name": zone["name"],
                    "city": "Marawi",
                    "province": "Lanao del Sur",
                    "center_latitude": zone["center_latitude"],
                    "center_longitude": zone["center_longitude"],
                    "boundary": zone["boundary"],
                    "barangay_names": zone["barangay_names"],
                    "priority": zone["priority"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded Marawi service zones: {created} created, {updated} updated."))
