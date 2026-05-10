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
        if not user.is_staff and not user.roles.filter(name__iexact="Merchant").exists():
            raise PermissionDenied("Only merchants can create stores.")

        serializer.save(owner=user)


from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from apps.orders.models import Order, OrderStatus, OrderItem
from django.shortcuts import get_object_or_404

class MerchantAnalyticsView(APIView):
    permission_classes = [IsMerchantOrAdmin]

    def get(self, request, store_id):
        store = get_object_or_404(Store, id=store_id)
        
        # Security Check
        if not request.user.is_staff and store.owner != request.user:
            raise PermissionDenied("You do not own this store.")

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)

        # 1. Financial Overview (Only Delivered orders count as Revenue)
        delivered_orders = Order.objects.filter(store=store, status=OrderStatus.DELIVERED)
        
        total_revenue = delivered_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_orders = delivered_orders.count()
        
        today_revenue = delivered_orders.filter(created_at__gte=today_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        today_orders = delivered_orders.filter(created_at__gte=today_start).count()

        # 2. Top Selling Products
        top_products = OrderItem.objects.filter(
            order__store=store, 
            order__status=OrderStatus.DELIVERED
        ).values(
            'product__name'
        ).annotate(
            total_sold=Sum('quantity')
        ).order_by('-total_sold')[:5]

        # 3. 7-Day Sales Trend
        sales_trend = delivered_orders.filter(
            created_at__gte=seven_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            daily_revenue=Sum('total_amount'),
            daily_orders=Count('id')
        ).order_by('date')

        return Response({
            "overview": {
                "total_revenue": float(total_revenue),
                "total_orders": total_orders,
                "today_revenue": float(today_revenue),
                "today_orders": today_orders,
            },
            "top_products": top_products,
            "sales_trend": list(sales_trend)
        })


class NearbyStoresView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        
        if not lat or not lng:
            return Response({"error": "Latitude and Longitude are required."}, status=400)

        from apps.riders.services import RiderDispatcherService
        
        stores = Store.objects.filter(is_active=True).select_related('vertical')
        
        results = []
        for store in stores:
            distance = RiderDispatcherService.haversine(
                float(lng), float(lat),
                float(store.longitude), float(store.latitude)
            )
            
            # Get average rating
            from django.db.models import Avg
            from apps.reviews.models import OrderReview
            avg_rating = OrderReview.objects.filter(store=store).aggregate(Avg('store_rating'))['store_rating__avg'] or 0

            results.append({
                "id": str(store.id),
                "name": store.name,
                "vertical": store.vertical.name if store.vertical else None,
                "address": store.street_address,
                "distance_km": round(distance, 2),
                "rating": round(avg_rating, 1),
                "is_open": store.is_open,
                "logo": store.image.url if store.image else None,
            })

        # Sort by distance
        results.sort(key=lambda x: x['distance_km'])

        return Response(results)
