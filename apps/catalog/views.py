from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Max, Q
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

from .models import Category, CategoryTemplate, InventoryMode, MedicineReference, Product, ProductReference
from .serializers import CategorySerializer, CategoryTemplateSerializer, MedicineReferenceSerializer, ProductReferenceSerializer, ProductSerializer


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


class CategoryTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategoryTemplateSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = CategoryTemplate.objects.select_related("vertical").filter(is_active=True)
        vertical = self.request.query_params.get("vertical", "").strip()
        query = self.request.query_params.get("q", "").strip()

        if vertical:
            queryset = queryset.filter(vertical__slug=vertical)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(slug__icontains=query)
            )
        return queryset.order_by("order", "name")[:50]


class ProductReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductReferenceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = ProductReference.objects.select_related("vertical").filter(is_active=True)
        vertical = self.request.query_params.get("vertical", "").strip()
        product_type = self.request.query_params.get("product_type", "").strip()
        query = self.request.query_params.get("q", "").strip()

        if vertical:
            queryset = queryset.filter(vertical__slug=vertical)
        if product_type:
            queryset = queryset.filter(product_type=product_type)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(brand_name__icontains=query)
                | Q(barcode__icontains=query)
                | Q(description__icontains=query)
            )
        return queryset.order_by("name", "brand_name")[:50]

    def list(self, request, *args, **kwargs):
        references = list(self.get_queryset())
        if references:
            return Response(self.get_serializer(references, many=True).data)

        vertical = request.query_params.get("vertical", "").strip()
        product_type = request.query_params.get("product_type", "").strip()
        query = request.query_params.get("q", "").strip()
        if not vertical or not product_type:
            return Response([])

        products = Product.objects.select_related(
            "category__store__vertical"
        ).filter(
            is_active=True,
            category__store__is_active=True,
            category__store__vertical__slug=vertical,
            product_type=product_type,
        )
        if query:
            products = products.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(sku__icontains=query)
                | Q(brand_name__icontains=query)
            )

        seen = set()
        payload = []
        for product in products.order_by("name", "sku")[:100]:
            key = (product.name.lower(), (product.sku or "").lower())
            if key in seen:
                continue
            seen.add(key)
            payload.append(
                {
                    "id": str(product.id),
                    "vertical": {
                        "id": str(product.category.store.vertical_id),
                        "name": product.category.store.vertical.name,
                        "slug": product.category.store.vertical.slug,
                    },
                    "name": product.name,
                    "brand_name": product.brand_name or "",
                    "barcode": product.sku or "",
                    "description": product.description or "",
                    "product_type": product.product_type,
                    "unit_type": product.unit_type or "",
                    "is_active": product.is_active,
                    "source": "Merchant catalog",
                }
            )
            if len(payload) >= 50:
                break

        return Response(payload)


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
    if product.stock_quantity <= product.low_stock_threshold:
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
        "low_stock_threshold": product.low_stock_threshold,
        "stock_status": stock_status,
        "availability_status": "AVAILABLE" if product.is_available and product.is_active else "UNAVAILABLE",
        "is_available": product.is_available,
        "image_url": request.build_absolute_uri(product.image.url) if product.image else "",
        "sku": product.sku or "",
        "product_type": product.product_type,
        "generic_name": product.generic_name or "",
        "brand_name": product.brand_name or "",
        "dosage": product.dosage or "",
        "medicine_form": product.medicine_form or "",
        "requires_prescription": product.requires_prescription,
        "medicine_reference": str(product.medicine_reference_id) if product.medicine_reference_id else "",
        "preparation_time_minutes": product.preparation_time_minutes,
        "updated_at": product.updated_at.isoformat(),
    }


def category_payload(category):
    product_count = getattr(category, "product_count", None)
    available_count = getattr(category, "available_product_count", None)
    unavailable_count = getattr(category, "unavailable_product_count", None)

    if product_count is None:
        product_count = category.products.count()
    if available_count is None:
        available_count = category.products.filter(is_active=True, is_available=True).count()
    if unavailable_count is None:
        unavailable_count = category.products.filter(Q(is_active=False) | Q(is_available=False)).count()

    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description or "",
        "is_active": category.is_active,
        "order": category.order,
        "product_count": product_count,
        "available_product_count": available_count,
        "unavailable_product_count": unavailable_count,
    }


def category_queryset_for_store(store):
    return (
        Category.objects.filter(store=store, is_active=True)
        .annotate(
            product_count=Count("products"),
            available_product_count=Count(
                "products",
                filter=Q(products__is_active=True, products__is_available=True),
            ),
            unavailable_product_count=Count(
                "products",
                filter=Q(products__is_active=False) | Q(products__is_available=False),
            ),
        )
        .order_by("order", "name")
    )


def unique_category_slug(store, name, category_id=None):
    base_slug = slugify(name)[:100] or "category"
    slug = base_slug
    counter = 2
    queryset = Category.objects.filter(store=store, slug=slug)
    if category_id:
        queryset = queryset.exclude(id=category_id)

    while queryset.exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:100 - len(suffix)]}{suffix}"
        queryset = Category.objects.filter(store=store, slug=slug)
        if category_id:
            queryset = queryset.exclude(id=category_id)
        counter += 1

    return slug


class CategoryManagementListView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        return Response(
            {
                "categories": [
                    category_payload(category)
                    for category in category_queryset_for_store(store)
                ]
            }
        )

    def post(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"name": "Category name is required."}, status=400)

        category = Category.objects.create(
            store=store,
            name=name,
            slug=unique_category_slug(store, name),
            description=str(request.data.get("description", "") or "").strip(),
            order=(Category.objects.filter(store=store).aggregate(max_order=Max("order"))["max_order"] or 0) + 1,
            is_active=True,
        )

        return Response(category_payload(category), status=status.HTTP_201_CREATED)


class CategoryManagementDetailView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, category_id):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        category = Category.objects.filter(id=category_id, store=store, is_active=True).first()
        if not category:
            return Response({"detail": "Category not found."}, status=404)

        if "name" in request.data:
            name = str(request.data.get("name", "")).strip()
            if not name:
                return Response({"name": "Category name is required."}, status=400)
            category.name = name
            category.slug = unique_category_slug(store, name, category_id=category.id)

        if "description" in request.data:
            category.description = str(request.data.get("description", "") or "").strip()
        category.save(update_fields=["name", "slug", "description"])
        return Response(category_payload(category))

    def delete(self, request, category_id):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        category = Category.objects.filter(id=category_id, store=store, is_active=True).first()
        if not category:
            return Response({"detail": "Category not found."}, status=404)

        if category.products.filter(is_active=True).exists():
            return Response(
                {"detail": "Move or delete products in this category first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category.is_active = False
        category.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryMoveView(APIView):
    permission_classes = [IsMerchant]

    def patch(self, request, category_id):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        direction = str(request.data.get("direction", "")).lower()
        if direction not in {"up", "down", "top", "bottom"}:
            return Response({"direction": "Use up, down, top, or bottom."}, status=400)

        category = Category.objects.filter(id=category_id, store=store, is_active=True).first()
        if not category:
            return Response({"detail": "Category not found."}, status=404)

        ordered_categories = list(
            Category.objects.filter(store=store, is_active=True).order_by("order", "name", "id")
        )
        current_index = next(
            (index for index, item in enumerate(ordered_categories) if item.id == category.id),
            None,
        )
        if current_index is None:
            return Response({"detail": "Category not found."}, status=404)

        if direction == "top":
            target_index = 0
        elif direction == "bottom":
            target_index = len(ordered_categories) - 1
        else:
            target_index = current_index - 1 if direction == "up" else current_index + 1

        if target_index < 0 or target_index >= len(ordered_categories) or target_index == current_index:
            return Response(
                {"categories": [category_payload(item) for item in category_queryset_for_store(store)]}
            )

        selected_category = ordered_categories.pop(current_index)
        ordered_categories.insert(target_index, selected_category)

        for index, item in enumerate(ordered_categories):
            if item.order != index:
                item.order = index
                item.save(update_fields=["order"])

        return Response(
            {"categories": [category_payload(item) for item in category_queryset_for_store(store)]}
        )


class CategoryReorderView(APIView):
    permission_classes = [IsMerchant]

    def patch(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        category_ids = request.data.get("category_ids")
        if not isinstance(category_ids, list) or not category_ids:
            return Response({"category_ids": "Provide category_ids as a non-empty list."}, status=400)

        categories = list(Category.objects.filter(store=store, is_active=True))
        category_map = {str(category.id): category for category in categories}

        if set(category_ids) != set(category_map.keys()):
            return Response(
                {"category_ids": "Category list must include every active category exactly once."},
                status=400,
            )

        for index, category_id in enumerate(category_ids):
            category = category_map[str(category_id)]
            if category.order != index:
                category.order = index
                category.save(update_fields=["order"])

        return Response(
            {"categories": [category_payload(item) for item in category_queryset_for_store(store)]}
        )


class ProductManagementListView(APIView):
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
                stock_quantity__lte=F("low_stock_threshold"),
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
        categories = category_queryset_for_store(store)
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
                        stock_quantity__lte=F("low_stock_threshold"),
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
                    category_payload(item)
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

        if store.vertical.slug == "restaurant":
            data["product_type"] = "food"
            data["inventory_mode"] = "none"
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


def store_product_or_none(user, product_id):
    store = get_or_create_merchant_store(user)
    if not store:
        return None, None

    product = Product.objects.select_related("category").filter(
        id=product_id,
        category__store=store,
    ).first()
    return store, product


class ProductManagementDetailView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, product_id):
        store, product = store_product_or_none(request.user, product_id)
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
        store, product = store_product_or_none(request.user, product_id)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        if not product:
            return Response({"detail": "Product not found."}, status=404)

        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductInventoryUpdateView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, product_id):
        store, product = store_product_or_none(request.user, product_id)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        if not product:
            return Response({"detail": "Product not found."}, status=404)

        track_inventory = request.data.get("track_inventory", product.track_inventory)
        if isinstance(track_inventory, str):
            track_inventory = track_inventory.lower() in {"true", "1", "yes", "on"}
        else:
            track_inventory = bool(track_inventory)

        is_available = request.data.get("is_available", product.is_available)
        if isinstance(is_available, str):
            is_available = is_available.lower() in {"true", "1", "yes", "on"}
        else:
            is_available = bool(is_available)

        data = {
            "inventory_mode": InventoryMode.SIMPLE_STOCK if track_inventory else InventoryMode.NONE,
            "track_inventory": track_inventory,
            "is_available": is_available,
        }

        if track_inventory:
            stock_quantity = request.data.get("stock_quantity")
            if stock_quantity in (None, ""):
                return Response({"stock_quantity": "Stock quantity is required."}, status=400)
            try:
                stock_quantity = int(stock_quantity)
            except (TypeError, ValueError):
                return Response({"stock_quantity": "Stock quantity must be a valid number."}, status=400)
            if stock_quantity < 0:
                return Response({"stock_quantity": "Stock quantity cannot be negative."}, status=400)
            data["stock_quantity"] = stock_quantity

            low_stock_threshold = request.data.get("low_stock_threshold", product.low_stock_threshold)
            if low_stock_threshold in (None, ""):
                low_stock_threshold = 5
            try:
                low_stock_threshold = int(low_stock_threshold)
            except (TypeError, ValueError):
                return Response({"low_stock_threshold": "Low stock threshold must be a valid number."}, status=400)
            if low_stock_threshold < 0:
                return Response({"low_stock_threshold": "Low stock threshold cannot be negative."}, status=400)
            data["low_stock_threshold"] = low_stock_threshold
        else:
            data["stock_quantity"] = None

        serializer = ProductSerializer(product, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        return Response(product_payload(product, request))

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
