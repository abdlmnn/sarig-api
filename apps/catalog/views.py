from rest_framework import viewsets, permissions
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        store_id = self.request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        return queryset


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True, is_available=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset


from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Avg
from apps.vendors.models import Store
from apps.riders.services import RiderDispatcherService # Use the haversine from here

class GlobalProductSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "")
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        
        # 1. Search Products
        products = Product.objects.select_related('category__store', 'category').filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
            is_available=True
        )

        results = []
        for product in products:
            store = product.category.store
            distance = None
            
            # 2. Calculate Distance if user location provided
            if lat and lng:
                distance = RiderDispatcherService.haversine(
                    float(lng), float(lat),
                    float(store.longitude), float(store.latitude)
                )
            
            results.append({
                "id": str(product.id),
                "name": product.name,
                "price": float(product.price),
                "store_name": store.name,
                "store_id": str(store.id),
                "distance_km": round(distance, 2) if distance is not None else None,
                "image": product.image.url if product.image else None,
            })

        # 3. Sort by Distance if possible
        if lat and lng:
            results.sort(key=lambda x: x['distance_km'] or 999)

        return Response(results)


class ProductComparisonView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        product_ids = request.query_params.getlist("ids") # Expecting ?ids=uuid1&ids=uuid2
        
        if len(product_ids) < 2:
            return Response({"error": "Please select at least 2 products to compare."}, status=400)

        products = Product.objects.filter(id__in=product_ids).select_related('store')
        
        comparison_data = []
        for p in products:
            # Get average rating for the store
            from apps.reviews.models import OrderReview
            avg_rating = OrderReview.objects.filter(store=p.store).aggregate(Avg('store_rating'))['store_rating__avg'] or 0

            comparison_data.append({
                "id": str(p.id),
                "name": p.name,
                "price": float(p.price),
                "description": p.description,
                "store_name": p.store.name,
                "store_rating": round(avg_rating, 1),
                "image": p.image.url if p.image else None,
            })

        return Response({
            "comparison": comparison_data,
            "smart_suggestion": self.get_smart_suggestion(comparison_data)
        })

    def get_smart_suggestion(self, data):
        if not data: return None
        
        # Simple logic: Best Value = (Rating / Price) * constant
        # For now, let's just highlight the Cheapest and the Best Rated
        cheapest = min(data, key=lambda x: x['price'])
        best_rated = max(data, key=lambda x: x['store_rating'])
        
        return {
            "cheapest_option": cheapest['name'],
            "best_rated_option": best_rated['name'],
            "verdict": f"If you're on a budget, go for {cheapest['name']}. If you want the best quality, {best_rated['name']} is the winner!"
        }
