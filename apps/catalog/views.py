from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.utils.text import slugify
from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import ApplicationStatus, MerchantApplication
from apps.onboarding.services import ApplicationService
from apps.riders.services import RiderDispatcherService
from apps.users.geo import get_lat_lng
from apps.users.permissions import IsMerchant
from apps.vendors.models import Store

from .models import Category, MedicineReference, Product
from .serializers import CategorySerializer, MedicineReferenceSerializer, ProductSerializer


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


class MedicineReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MedicineReferenceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = MedicineReference.objects.filter(is_active=True)
        query = self.request.query_params.get("q", "").strip()
        requires_prescription = self.request.query_params.get("requires_prescription")
        if query:
            queryset = queryset.filter(
                Q(generic_name__icontains=query)
                | Q(brand_name__icontains=query)
                | Q(registration_number__icontains=query)
                | Q(pharmacologic_category__icontains=query)
            )
        if requires_prescription in ("true", "false"):
            queryset = queryset.filter(requires_prescription=requires_prescription == "true")
        return queryset[:50]


def get_or_create_merchant_store(user):
    store = Store.objects.filter(owner=user, is_active=True).first()
    if store:
        return store

    application = (
        MerchantApplication.objects.filter(
            applicant=user,
            status=ApplicationStatus.APPROVED,
        )
        .order_by("-updated_at")
        .first()
    )
    if not application:
        return None

    return ApplicationService.create_store_for_merchant(application)


def money_payload(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    return {
        "value": str(amount),
        "currency": "PHP",
        "formatted": f"₱{amount:,.0f}",
    }


def product_stock_status(product):
    if not product.track_inventory:
        return "NOT_TRACKED"
    if not product.stock_quantity:
        return "OUT_OF_STOCK"
    if product.stock_quantity <= 5:
        return "LOW_STOCK"
    return "IN_STOCK"


def product_payload(product, request):
    stock_status = product_stock_status(product)
    return {
        "id": str(product.id),
        "name": product.name,
        "description": product.description or "",
        "category": {
            "id": str(product.category_id),
            "name": product.category.name,
            "slug": product.category.slug,
        },
        "price": money_payload(product.price),
        "stock_quantity": product.stock_quantity if product.track_inventory else None,
        "track_inventory": product.track_inventory,
        "low_stock_threshold": 5,
        "stock_status": stock_status,
        "availability_status": "AVAILABLE" if product.is_available and product.is_active else "UNAVAILABLE",
        "is_available": product.is_available,
        "image_url": request.build_absolute_uri(product.image.url) if product.image else "",
        "sku": product.sku or "",
        "preparation_time_minutes": product.preparation_time_minutes,
        "updated_at": product.updated_at.isoformat(),
    }


def merchant_product_or_none(user, product_id):
    store = get_or_create_merchant_store(user)
    if not store:
        return None, None

    product = Product.objects.select_related("category").filter(
        id=product_id,
        category__store=store,
    ).first()
    return store, product


class MerchantProductListView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        query = request.query_params.get("q", "").strip()
        category = request.query_params.get("category", "ALL")
        status_filter = request.query_params.get("status", "ALL")
        sort = request.query_params.get("sort", "newest")
        page = max(int(request.query_params.get("page", "1") or 1), 1)
        page_size = min(max(int(request.query_params.get("page_size", "10") or 10), 1), 50)

        base_products = Product.objects.select_related("category").filter(category__store=store)
        all_products = base_products
        filtered_products = base_products

        if query:
            filtered_products = filtered_products.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(slug__icontains=query)
                | Q(sku__icontains=query)
            )
        if category and category != "ALL":
            filtered_products = filtered_products.filter(category__slug=category)
        if status_filter == "AVAILABLE":
            filtered_products = filtered_products.filter(is_active=True, is_available=True)
        elif status_filter == "UNAVAILABLE":
            filtered_products = filtered_products.filter(Q(is_active=False) | Q(is_available=False))
        elif status_filter == "LOW_STOCK":
            filtered_products = filtered_products.filter(
                track_inventory=True,
                stock_quantity__gt=0,
                stock_quantity__lte=5,
            )
        elif status_filter == "OUT_OF_STOCK":
            filtered_products = filtered_products.filter(
                track_inventory=True,
                stock_quantity__lte=0,
            )

        sort_map = {
            "name_asc": "name",
            "name_desc": "-name",
            "newest": "-created_at",
            "oldest": "created_at",
            "price_asc": "price",
            "price_desc": "-price",
        }
        paginator = Paginator(filtered_products.order_by(sort_map.get(sort, "-created_at")), page_size)
        page_obj = paginator.get_page(page)
        categories = Category.objects.filter(store=store, is_active=True).order_by("order", "name")
        inventory_enabled = (
            store.vertical.slug != "restaurant"
            and all_products.filter(track_inventory=True).exists()
        )

        return Response(
            {
                "summary": {
                    "total_products": all_products.count(),
                    "available_products": all_products.filter(is_active=True, is_available=True).count(),
                    "unavailable_products": all_products.filter(Q(is_active=False) | Q(is_available=False)).count(),
                    "low_stock_products": all_products.filter(
                        track_inventory=True,
                        stock_quantity__gt=0,
                        stock_quantity__lte=5,
                    ).count(),
                },
                "merchant": {
                    "business_name": store.name,
                    "vertical": {
                        "id": str(store.vertical_id),
                        "name": store.vertical.name,
                        "slug": store.vertical.slug,
                    },
                },
                "categories": [
                    {"id": str(item.id), "name": item.name, "slug": item.slug}
                    for item in categories
                ],
                "products": [
                    product_payload(product, request)
                    for product in page_obj.object_list
                ],
                "pagination": {
                    "page": page_obj.number,
                    "page_size": page_size,
                    "total_pages": paginator.num_pages or 1,
                    "total_items": paginator.count,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                },
                "inventory_enabled": inventory_enabled,
            }
        )

    def post(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        category_id = request.data.get("category")
        category = Category.objects.filter(id=category_id, store=store, is_active=True).first()
        if not category:
            return Response({"category": "Select a valid category for this store."}, status=400)

        data = request.data.copy()
        data["category"] = str(category.id)
        data["product_type"] = data.get("product_type") or "food"
        data["inventory_mode"] = data.get("inventory_mode") or "none"
        data["track_inventory"] = False
        data["stock_quantity"] = None

        name = str(data.get("name", "")).strip()
        if name and not data.get("slug"):
            base_slug = slugify(name)[:240] or "product"
            slug = base_slug
            counter = 2
            while Product.objects.filter(category__store=store, slug=slug).exists():
                suffix = f"-{counter}"
                slug = f"{base_slug[:240 - len(suffix)]}{suffix}"
                counter += 1
            data["slug"] = slug

        serializer = ProductSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        return Response(product_payload(product, request), status=status.HTTP_201_CREATED)


class MerchantProductDetailView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, product_id):
        store, product = merchant_product_or_none(request.user, product_id)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        if not product:
            return Response({"detail": "Product not found."}, status=404)

        data = request.data.copy()
        category_id = data.get("category")
        if category_id:
            category = Category.objects.filter(id=category_id, store=store, is_active=True).first()
            if not category:
                return Response({"category": "Select a valid category for this store."}, status=400)
            data["category"] = str(category.id)

        data["product_type"] = data.get("product_type") or product.product_type
        data["inventory_mode"] = data.get("inventory_mode") or product.inventory_mode
        if store.vertical.slug == "restaurant":
            data["product_type"] = "food"
            data["inventory_mode"] = "none"
            data["track_inventory"] = False
            data["stock_quantity"] = None

        serializer = ProductSerializer(product, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        return Response(product_payload(product, request))

    def delete(self, request, product_id):
        store, product = merchant_product_or_none(request.user, product_id)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        if not product:
            return Response({"detail": "Product not found."}, status=404)

        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class GlobalProductSearchView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request):
        query = request.query_params.get("q", "")
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        has_location = lat not in (None, "") or lng not in (None, "")

        if has_location:
            if not lat or not lng:
                return Response({"error": "Latitude and longitude must be provided together."}, status=400)
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (TypeError, ValueError):
                return Response({"error": "Invalid latitude/longitude values."}, status=400)
            if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
                return Response({"error": "Latitude/longitude out of valid range."}, status=400)
        
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
            if has_location:
                store_lat, store_lng = get_lat_lng(store, "latitude", "longitude")
                distance = RiderDispatcherService.haversine(
                    lng_f, lat_f,
                    float(store_lng), float(store_lat)
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
        if has_location:
            results.sort(key=lambda x: x['distance_km'] or 999)

        return Response(results)


class ProductComparisonView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request):
        product_ids = request.query_params.getlist("ids") # Expecting ?ids=uuid1&ids=uuid2
        
        if len(product_ids) < 2:
            return Response({"error": "Please select at least 2 products to compare."}, status=400)

        products = Product.objects.filter(id__in=product_ids).select_related('category__store')
        
        comparison_data = []
        for p in products:
            # Get average rating for the store
            from apps.reviews.models import OrderReview
            store = p.category.store
            avg_rating = OrderReview.objects.filter(store=store).aggregate(Avg('store_rating'))['store_rating__avg'] or 0

            comparison_data.append({
                "id": str(p.id),
                "name": p.name,
                "price": float(p.price),
                "description": p.description,
                "store_name": store.name,
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
