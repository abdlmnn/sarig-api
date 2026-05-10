from django.conf import settings
from django.core.management.base import BaseCommand
from apps.vendors.models import Store
from apps.riders.models import RiderProfile
from apps.users.geo import get_lat_lng, to_wkt_point


class Command(BaseCommand):
    help = "Phase 2A dry-run helper: previews lat/lng -> WKT point mapping without writing DB spatial fields."

    def handle(self, *args, **options):
        if not getattr(settings, "USE_POSTGIS", False):
            self.stdout.write(self.style.WARNING("USE_POSTGIS is disabled. Preview still works, but no spatial write is attempted."))

        stores = Store.objects.filter(latitude__isnull=False, longitude__isnull=False).count()
        riders = RiderProfile.objects.filter(current_latitude__isnull=False, current_longitude__isnull=False).count()

        self.stdout.write(self.style.SUCCESS(f"Store coordinates available: {stores}"))
        self.stdout.write(self.style.SUCCESS(f"Rider coordinates available: {riders}"))

        sample_store = Store.objects.filter(latitude__isnull=False, longitude__isnull=False).first()
        if sample_store:
            lat, lng = get_lat_lng(sample_store, "latitude", "longitude")
            self.stdout.write(f"Sample Store WKT: {to_wkt_point(lat, lng)}")

        sample_rider = RiderProfile.objects.filter(
            current_latitude__isnull=False, current_longitude__isnull=False
        ).first()
        if sample_rider:
            lat, lng = get_lat_lng(sample_rider, "current_latitude", "current_longitude")
            self.stdout.write(f"Sample Rider WKT: {to_wkt_point(lat, lng)}")
