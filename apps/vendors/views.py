import logging

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Avg
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.realtime import broadcast_realtime_event
from apps.riders.services import RiderDispatcherService
from apps.users.geo import get_lat_lng
from apps.users.permissions import IsMerchant
from .models import Store, BusinessVertical
from .serializers import (
    BusinessVerticalSerializer,
    StoreBrandingSerializer,
    StoreSerializer,
    StoreStatusUpdateSerializer,
)
from .permissions import IsMerchantOrAdmin
from .utils import PH_TZ, store_availability_payload

logger = logging.getLogger(__name__)


class BusinessVerticalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BusinessVerticalSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return BusinessVertical.objects.filter(
            is_active=True,
            slug__in=[
                "restaurant",
                "pharmacy",
                "grocery",
                "market",
                "convenience-store",
                "general-store",
                "bakery",
            ],
        )


class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [IsMerchantOrAdmin]

    def get_queryset(self):
        queryset = Store.objects.select_related("vertical", "owner")

        # Own stores only (Filter merchant)
        user = self.request.user

        # only own stores unless admin
        if not user.is_staff:
            queryset = queryset.filter(owner=user)

        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")
        radius = self.request.query_params.get("radius")

        # Optional geo filter for staff/ops listing, dual-mode safe.
        if lat and lng and radius:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                radius_f = float(radius)
            except (TypeError, ValueError):
                return queryset

            if getattr(settings, "USE_POSTGIS", False):
                try:
                    user_location = Point(lng_f, lat_f, srid=4326)
                    return (
                        queryset.filter(location_point__isnull=False)
                        .filter(location_point__distance_lte=(user_location, D(km=radius_f)))
                        .annotate(distance=Distance("location_point", user_location))
                        .order_by("distance")
                    )
                except (ValueError, TypeError) as exc:
                    logger.warning("StoreViewSet PostGIS geo filter fallback due to invalid input: %s", exc)
                except Exception as exc:
                    logger.warning("StoreViewSet PostGIS geo filter fallback due to runtime error: %s", exc)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        # ensure only merchants can create stores
        if not user.is_staff and not user.roles.filter(name__iexact="Merchant").exists():
            raise PermissionDenied("Only merchants can create stores.")

        serializer.save(owner=user)


class NearbyStoresView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "nearby_stores"

    def get(self, request):
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius = request.query_params.get("radius")
        
        if not lat or not lng:
            return Response({"error": "Latitude and Longitude are required."}, status=400)
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            radius_f = float(radius) if radius is not None else None
        except (TypeError, ValueError):
            return Response({"error": "Invalid latitude/longitude/radius values."}, status=400)
        if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
            return Response({"error": "Latitude/Longitude out of valid range."}, status=400)
        if radius_f is not None and radius_f <= 0:
            return Response({"error": "Radius must be greater than 0."}, status=400)

        stores = (
            Store.objects.filter(is_active=True)
            .select_related("vertical")
            .annotate(avg_store_rating=Avg("reviews__store_rating"))
        )

        results = []

        # Prefer PostGIS query path, but keep Haversine fallback for dual-mode rollout.
        if getattr(settings, "USE_POSTGIS", False):
            try:
                user_point = Point(lng_f, lat_f, srid=4326)
                stores = stores.filter(location_point__isnull=False)
                if radius_f is not None:
                    stores = stores.filter(location_point__distance_lte=(user_point, D(km=radius_f)))
                stores = stores.annotate(distance=Distance("location_point", user_point)).order_by("distance")
            except (ValueError, TypeError) as exc:
                logger.warning("NearbyStoresView PostGIS fallback due to invalid geo input: %s", exc)
            except Exception as exc:
                logger.warning("NearbyStoresView PostGIS fallback due to runtime error: %s", exc)

        for store in stores:
            store_lat, store_lng = get_lat_lng(store, "latitude", "longitude")
            if hasattr(store, "distance") and store.distance is not None:
                distance = float(
                    store.distance.km if hasattr(store.distance, "km") else store.distance
                )
            else:
                distance = RiderDispatcherService.haversine(
                    lng_f,
                    lat_f,
                    float(store_lng),
                    float(store_lat),
                )
                if radius_f is not None and distance > radius_f:
                    continue

            avg_rating = store.avg_store_rating or 0

            results.append({
                "id": str(store.id),
                "name": store.name,
                "vertical": store.vertical.name if store.vertical else None,
                "address": store.street_address,
                "distance_km": round(distance, 2),
                "rating": round(avg_rating, 1),
                "is_open": store.is_open,
                "logo": store.logo_image.url if store.logo_image else None,
            })

        # Ensure stable ordering when fallback path is used.
        results.sort(key=lambda x: x["distance_km"])

        return Response(results)


class MerchantDashboardOverviewView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def get(self, request):
        stores = list(request.user.stores.select_related("vertical").filter(is_active=True).order_by("name"))
        if not stores:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        if any(not store.logo_image for store in stores):
            return Response(
                {
                    "code": "STORE_LOGO_REQUIRED",
                    "detail": "Add a logo for every active store before opening the dashboard.",
                },
                status=428,
            )

        primary_store = stores[0]
        availability = store_availability_payload(primary_store, timezone.now().astimezone(PH_TZ))
        return Response(
            {
                "merchant": {
                    "id": str(request.user.id),
                    "business_name": (
                        primary_store.name
                        if len(stores) == 1
                        else f"{primary_store.name} + {len(stores) - 1} more"
                    ),
                    **availability,
                    "service_modes": ["DELIVERY", "PICKUP"],
                    "last_updated": max(store.updated_at for store in stores).astimezone(PH_TZ).isoformat(),
                }
            }
        )


class MerchantStoreStatusView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def patch(self, request):
        store = request.user.stores.filter(is_active=True).order_by("name").first()
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        serializer = StoreStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        store.manual_override = serializer.validated_data.get("manual_override")
        store.manual_override_reason = serializer.validated_data.get("reason", "")
        store.save(update_fields=["manual_override", "manual_override_reason", "updated_at"])

        availability = store_availability_payload(store, timezone.now().astimezone(PH_TZ))
        broadcast_realtime_event(
            "store_status_changed",
            {"store_id": str(store.id), **availability},
        )
        return Response(
            {
                "store_id": str(store.id),
                **availability,
            }
        )


class MerchantStoreBrandingListView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def get(self, request):
        stores = request.user.stores.filter(is_active=True).order_by("name")
        return Response(
            {
                "stores": StoreBrandingSerializer(
                    stores,
                    many=True,
                    context={"request": request},
                ).data
            }
        )


class MerchantStoreBrandingDetailView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "search"

    def patch(self, request, store_id):
        store = request.user.stores.filter(id=store_id, is_active=True).first()
        if not store:
            return Response(
                {"detail": "Store not found."},
                status=404,
            )
        serializer = StoreBrandingSerializer(
            store,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
