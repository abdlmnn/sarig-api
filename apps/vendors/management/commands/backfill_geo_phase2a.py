from django.core.management.base import BaseCommand
from apps.vendors.models import Store
from apps.riders.models import RiderProfile
from apps.users.geo import get_lat_lng, to_wkt_point
from django.contrib.gis.geos import Point


class Command(BaseCommand):
    help = "Phase 3 geo helper: backfills WKT and Point columns from decimal lat/lng (dual-mode write)."

    def handle(self, *args, **options):
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

        store_wkt_updates = 0
        store_point_updates = 0
        for store in Store.objects.filter(latitude__isnull=False, longitude__isnull=False):
            lat, lng = get_lat_lng(store, "latitude", "longitude")
            new_wkt = to_wkt_point(lat, lng)
            new_point = Point(float(lng), float(lat), srid=4326)
            changed_fields = []
            if store.location_wkt != new_wkt:
                store.location_wkt = new_wkt
                changed_fields.append("location_wkt")
                store_wkt_updates += 1
            if store.location_point != new_point:
                store.location_point = new_point
                changed_fields.append("location_point")
                store_point_updates += 1
            if changed_fields:
                store.save(update_fields=changed_fields)

        rider_wkt_updates = 0
        rider_point_updates = 0
        for rider in RiderProfile.objects.filter(
            current_latitude__isnull=False, current_longitude__isnull=False
        ):
            lat, lng = get_lat_lng(rider, "current_latitude", "current_longitude")
            new_wkt = to_wkt_point(lat, lng)
            new_point = Point(float(lng), float(lat), srid=4326)
            changed_fields = []
            if rider.location_wkt != new_wkt:
                rider.location_wkt = new_wkt
                changed_fields.append("location_wkt")
                rider_wkt_updates += 1
            if rider.location_point != new_point:
                rider.location_point = new_point
                changed_fields.append("location_point")
                rider_point_updates += 1
            if changed_fields:
                rider.save(update_fields=changed_fields)

        self.stdout.write(self.style.SUCCESS(f"Backfilled store location_wkt rows: {store_wkt_updates}"))
        self.stdout.write(self.style.SUCCESS(f"Backfilled store location_point rows: {store_point_updates}"))
        self.stdout.write(self.style.SUCCESS(f"Backfilled rider location_wkt rows: {rider_wkt_updates}"))
        self.stdout.write(self.style.SUCCESS(f"Backfilled rider location_point rows: {rider_point_updates}"))
