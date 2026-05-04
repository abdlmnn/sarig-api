from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Store, BusinessVertical
from .serializers import StoreSerializer, BusinessVerticalSerializer
from .permissions import IsMerchantOrAdmin

# from django.contrib.gis.geos import Point
# from django.contrib.gis.db.models.functions import Distance
# from django.contrib.gis.measure import D


class BusinessVerticalViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessVerticalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BusinessVertical.objects.filter(is_active=True)


class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [IsMerchantOrAdmin]

    def get_queryset(self):
        queryset = Store.objects.select_related("vertical", "owner")

        # OPTIONAL GEO FILTER (READY FOR FUTURE)
        # lat = self.request.query_params.get("lat")
        # lng = self.request.query_params.get("lng")
        # radius = self.request.query_params.get("radius")

        # if lat and lng and radius:
        #     user_location = Point(float(lng), float(lat), srid=4326)

        #     queryset = (
        #         queryset.filter(
        #             location__distance_lte=(user_location, D(km=float(radius)))
        #         )
        #         .annotate(distance=Distance("location", user_location))
        #         .order_by("distance")
        #     )

        # Own stores only (Filter merchant)
        user = self.request.user

        # only own stores unless admin
        if not user.is_staff:
            queryset = queryset.filter(owner=user)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        # ensure only merchants can create stores
        if not user.is_staff and not user.roles.filter(name="merchant").exists():
            raise PermissionDenied("Only merchants can create stores.")

        serializer.save(owner=user)
