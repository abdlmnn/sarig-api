from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    DeliveryFeeEstimateSerializer,
    LocationSearchQuerySerializer,
    ReverseGeocodeSerializer,
    RouteEstimateSerializer,
)
from .services import GeoapifyService, LocationProviderError, calculate_delivery_fee, route_estimate


class LocationSearchView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "locations"

    def get(self, request):
        serializer = LocationSearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            results = GeoapifyService.search(data["q"], data["limit"])
        except LocationProviderError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"results": results})


class ReverseGeocodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "locations"

    def post(self, request):
        serializer = ReverseGeocodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = GeoapifyService.reverse(data["latitude"], data["longitude"])
        except LocationProviderError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if result is None:
            return Response({"error": "No address found for this location."}, status=404)
        return Response(result)


class RouteEstimateView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "locations"

    def post(self, request):
        serializer = RouteEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(route_estimate(data["origin"], data["destination"]))


class DeliveryFeeEstimateView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "locations"

    def post(self, request):
        serializer = DeliveryFeeEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        estimate = route_estimate(data["store"], data["customer"])
        if float(estimate["distance_km"]) > settings.DELIVERY_MAX_DISTANCE_KM:
            return Response(
                {"error": "Delivery address is outside the supported distance."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        estimate["delivery_fee"] = calculate_delivery_fee(estimate["distance_km"])
        return Response(estimate)
