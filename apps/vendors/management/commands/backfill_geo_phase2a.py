from django.conf import settings
from django.core.management.base import BaseCommand
from apps.vendors.models import Store
from apps.riders.models import RiderProfile
from apps.users.geo import get_lat_lng, to_wkt_point


class Command(BaseCommand):
    help = "Phase 2 geo helper: backfills WKT columns from decimal lat/lng (safe dual-mode write)."

    def handle(self, *args, **options):
        if not getattr(settings, "USE_POSTGIS", False):
            self.stdout.write(self.style.WARNING("USE_POSTGIS is disabled. WKT backfill still works for dual-mode compatibility."))

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

        store_updates = 0
        for store in Store.objects.filter(latitude__isnull=False, longitude__isnull=False):
            lat, lng = get_lat_lng(store, "latitude", "longitude")
            new_wkt = to_wkt_point(lat, lng)
            if store.location_wkt != new_wkt:
                store.location_wkt = new_wkt
                store.save(update_fields=["location_wkt"])
                store_updates += 1

        rider_updates = 0
        for rider in RiderProfile.objects.filter(
            current_latitude__isnull=False, current_longitude__isnull=False
        ):
            lat, lng = get_lat_lng(rider, "current_latitude", "current_longitude")
            new_wkt = to_wkt_point(lat, lng)
            if rider.location_wkt != new_wkt:
                rider.location_wkt = new_wkt
                rider.save(update_fields=["location_wkt"])
                rider_updates += 1

        self.stdout.write(self.style.SUCCESS(f"Backfilled store location_wkt rows: {store_updates}"))
        self.stdout.write(self.style.SUCCESS(f"Backfilled rider location_wkt rows: {rider_updates}"))
