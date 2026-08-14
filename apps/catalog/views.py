import json
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    Max,
    Min,
    Prefetch,
    Q,
    Value,
    When,
)
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.money import money_payload
from apps.onboarding.models import ApplicationStatus, MerchantApplication
from apps.onboarding.services import ApplicationService
from apps.locations.services import calculate_delivery_fee
from apps.riders.services import RiderDispatcherService
from apps.users.geo import get_lat_lng
from apps.users.permissions import IsMerchant
from apps.vendors.models import Store
from apps.vendors.utils import PH_TZ, store_availability_payload

from .models import (
    Category,
    CategoryTemplate,
    InventoryMode,
    MedicineReference,
    ModifierGroup,
    ModifierItem,
    Product,
    ProductReference,
)
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
    permission_classes = [permissions.IsAuthenticated]

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
        "image_url": product_image_url(product, request),
        "sku": product.sku or "",
        "product_type": product.product_type,
        "generic_name": product.generic_name or "",
        "brand_name": product.brand_name or "",
        "dosage": product.dosage or "",
        "medicine_form": product.medicine_form or "",
        "requires_prescription": product.requires_prescription,
        "medicine_reference": str(product.medicine_reference_id) if product.medicine_reference_id else "",
        "preparation_time_minutes": product.preparation_time_minutes,
        "modifier_groups": modifier_groups_payload(product, request),
        "updated_at": product.updated_at.isoformat(),
    }


def modifier_groups_payload(product, request):
    return [
        {
            "id": str(group.id),
            "name": group.name,
            "is_required": group.is_required,
            "max_selections": group.items.filter(is_available=True).count(),
            "items": [
                {
                    "id": str(item.id),
                    "linked_product": str(item.linked_product_id) if item.linked_product_id else "",
                    "image_url": product_image_url(item.linked_product, request)
                    if item.linked_product_id
                    else "",
                    "name": item.name,
                    "extra_price": str(item.extra_price),
                    "is_available": item.is_available,
                }
                for item in group.items.all()
            ],
        }
        for group in product.modifier_groups.all()
    ]


def product_image_url(product, request):
    if not product.image:
        return ""

    try:
        return request.build_absolute_uri(product.image.url)
    except ValueError:
        return ""


def marketplace_store_availability(store):
    return store_availability_payload(store, timezone.now().astimezone(PH_TZ))


def marketplace_store_is_open(store):
    return marketplace_store_availability(store)["status"] == "OPEN"


def mutable_request_data(data):
    if hasattr(data, "dict"):
        normalized = data.dict()
    else:
        normalized = dict(data)
    return {
        key: value
        for key, value in normalized.items()
        if value not in (None, "")
    }


def parse_modifier_groups_payload(raw_value, store=None):
    if raw_value in (None, ""):
        return None, ""

    try:
        groups = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (TypeError, json.JSONDecodeError):
        return None, "Use a valid modifier group list."

    if not isinstance(groups, list):
        return None, "Use a valid modifier group list."

    normalized_groups = []
    for group in groups[:12]:
        if not isinstance(group, dict):
            return None, "Each modifier group must be an object."
        name = str(group.get("name", "")).strip()
        if not name:
            continue
        try:
            max_selections = int(group.get("max_selections") or 1)
        except (TypeError, ValueError):
            return None, f"{name} has an invalid max selection value."
        max_selections = min(max(max_selections, 1), 20)

        items = []
        raw_items = group.get("items", [])
        if not isinstance(raw_items, list):
            return None, f"{name} options must be a list."
        for item in raw_items[:40]:
            if not isinstance(item, dict):
                return None, f"{name} has an invalid option."
            item_name = str(item.get("name", "")).strip()
            if not item_name:
                continue
            try:
                extra_price = Decimal(str(item.get("extra_price") or "0"))
            except Exception:
                return None, f"{item_name} has an invalid price."
            if extra_price < 0:
                return None, f"{item_name} price cannot be negative."
            linked_product = None
            linked_product_id = str(item.get("linked_product") or "").strip()
            if linked_product_id:
                linked_product = Product.objects.filter(
                    id=linked_product_id,
                    category__store=store,
                    is_active=True,
                ).first()
                if not linked_product:
                    return None, f"{item_name} uses an invalid product link."
            items.append(
                {
                    "name": item_name[:100],
                    "extra_price": extra_price,
                    "is_available": bool(item.get("is_available", True)),
                    "linked_product": linked_product,
                }
            )
        if items:
            normalized_groups.append(
                {
                    "name": name[:100],
                    "is_required": bool(group.get("is_required", False)),
                    "max_selections": min(max_selections, len(items)),
                    "items": items,
                }
            )
    return normalized_groups, ""


def replace_product_modifier_groups(product, groups):
    product.modifier_groups.all().delete()
    if not groups:
        return

    for group_data in groups:
        group = ModifierGroup.objects.create(
            product=product,
            name=group_data["name"],
            is_required=group_data["is_required"],
            max_selections=group_data["max_selections"],
        )
        ModifierItem.objects.bulk_create(
            [
                ModifierItem(
                    group=group,
                    name=item["name"],
                    extra_price=item["extra_price"],
                    is_available=item["is_available"],
                    linked_product=item["linked_product"],
                )
                for item in group_data["items"]
            ]
        )


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

        base_products = (
            Product.objects.select_related("category")
            .prefetch_related(
                Prefetch(
                    "modifier_groups__items",
                    queryset=ModifierItem.objects.select_related("linked_product"),
                )
            )
            .filter(category__store=store)
        )
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

        data = mutable_request_data(request.data)
        modifier_groups, modifier_error = parse_modifier_groups_payload(
            data.pop("modifier_groups", None),
            store,
        )
        if modifier_error:
            return Response({"modifier_groups": modifier_error}, status=400)
        data["category"] = str(category.id)
        data["product_type"] = data.get("product_type") or "food"
        data["inventory_mode"] = data.get("inventory_mode") or "none"

        if store.vertical.slug == "restaurant":
            data["product_type"] = "food"
            data["inventory_mode"] = "none"
            data["track_inventory"] = False
            data.pop("stock_quantity", None)

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
        if store.vertical.slug == "restaurant":
            replace_product_modifier_groups(product, modifier_groups)

        return Response(product_payload(product, request), status=status.HTTP_201_CREATED)


def store_product_or_none(user, product_id):
    store = get_or_create_merchant_store(user)
    if not store:
        return None, None

    product = Product.objects.select_related("category").prefetch_related(
        Prefetch(
            "modifier_groups__items",
            queryset=ModifierItem.objects.select_related("linked_product"),
        ),
    ).filter(
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

        data = mutable_request_data(request.data)
        modifier_groups, modifier_error = parse_modifier_groups_payload(
            data.pop("modifier_groups", None),
            store,
        )
        if modifier_error:
            return Response({"modifier_groups": modifier_error}, status=400)
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
            data.pop("stock_quantity", None)

        serializer = ProductSerializer(product, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        if store.vertical.slug == "restaurant" and modifier_groups is not None:
            replace_product_modifier_groups(product, modifier_groups)

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
        filters, error = self.parse_filters(request)
        if error:
            return error

        products = self.product_queryset(filters)
        facets = {
            "verticals": self.vertical_facets(),
            "categories": self.category_facets(filters["vertical"]),
        }
        total_items = products.count()
        start = (filters["page"] - 1) * filters["page_size"]
        end = start + filters["page_size"]

        if filters["sort"] == "nearest":
            results = [
                self.result_payload(product, request, filters)
                for product in products
            ]
            results.sort(
                key=lambda item: (
                    not item["store"]["is_open"],
                    item["distance_km"] is None,
                    item["distance_km"] or 0,
                    item["name"],
                )
            )
            page_results = results[start:end]
        else:
            page_results = [
                self.result_payload(product, request, filters)
                for product in products[start:end]
            ]

        total_pages = max(1, (total_items + filters["page_size"] - 1) // filters["page_size"])

        return Response(
            {
                "results": page_results,
                "facets": facets,
                "pagination": {
                    "page": filters["page"],
                    "page_size": filters["page_size"],
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": filters["page"] < total_pages,
                    "has_previous": filters["page"] > 1,
                },
            }
        )

    def parse_filters(self, request):
        query = request.query_params.get("q", "").strip()[:120]
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        location, error = self.parse_location(lat, lng)
        if error:
            return None, error

        try:
            min_price = self.parse_price(request.query_params.get("min_price"))
            max_price = self.parse_price(request.query_params.get("max_price"))
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(48, max(1, int(request.query_params.get("page_size", 24))))
        except (TypeError, ValueError):
            return None, Response(
                {"error": "Price and pagination filters must be valid numbers."},
                status=400,
            )

        if min_price is not None and max_price is not None and min_price > max_price:
            return None, Response(
                {"error": "Minimum price cannot be greater than maximum price."},
                status=400,
            )

        sort = request.query_params.get("sort", "relevance")
        allowed_sorts = {"relevance", "nearest", "price_low", "price_high", "rating"}
        if sort not in allowed_sorts:
            return None, Response({"error": "Invalid sort option."}, status=400)
        if sort == "nearest" and not location:
            sort = "relevance"

        return {
            "query": query,
            "vertical": request.query_params.get("vertical", "").strip(),
            "category": request.query_params.get("category", "").strip(),
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort,
            "location": location,
            "page": page,
            "page_size": page_size,
        }, None

    @staticmethod
    def parse_price(value):
        if value in (None, ""):
            return None
        amount = Decimal(value)
        if amount < 0:
            raise ValueError
        return amount

    @staticmethod
    def parse_location(lat, lng):
        if lat in (None, "") and lng in (None, ""):
            return None, None
        if not lat or not lng:
            return None, Response(
                {"error": "Latitude and longitude must be provided together."},
                status=400,
            )
        try:
            latitude = float(lat)
            longitude = float(lng)
        except (TypeError, ValueError):
            return None, Response(
                {"error": "Invalid latitude/longitude values."},
                status=400,
            )
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return None, Response(
                {"error": "Latitude/longitude out of valid range."},
                status=400,
            )
        return (latitude, longitude), None

    @staticmethod
    def base_queryset():
        return Product.objects.select_related(
            "category",
            "category__store",
            "category__store__vertical",
        ).prefetch_related(
            Prefetch(
                "modifier_groups__items",
                queryset=ModifierItem.objects.select_related("linked_product"),
            ),
        ).filter(
            is_active=True,
            is_available=True,
            category__is_active=True,
            category__store__is_active=True,
            category__store__vertical__is_active=True,
        ).filter(
            Q(track_inventory=False) | Q(stock_quantity__gt=0)
        )

    def product_queryset(self, filters):
        products = self.base_queryset()
        query = filters["query"]
        if query:
            products = products.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(brand_name__icontains=query)
                | Q(generic_name__icontains=query)
                | Q(category__store__name__icontains=query)
            )
        if filters["vertical"]:
            products = products.filter(
                category__store__vertical__slug=filters["vertical"]
            )
        if filters["category"]:
            products = products.filter(category__slug=filters["category"])
        if filters["min_price"] is not None:
            products = products.filter(price__gte=filters["min_price"])
        if filters["max_price"] is not None:
            products = products.filter(price__lte=filters["max_price"])
        ordering = {
            "relevance": ("name", "price"),
            "price_low": ("price", "name"),
            "price_high": ("-price", "name"),
            "rating": ("-category__store__rating", "name"),
            "nearest": ("name",),
        }
        effective_open = Case(
            When(
                category__store__is_open=True,
                category__store__manual_override__isnull=True,
                then=Value(0),
            ),
            When(
                category__store__is_open=True,
                category__store__manual_override__in=["", "OPEN_NOW"],
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        )
        return products.order_by(
            effective_open,
            *ordering[filters["sort"]],
        )

    def vertical_facets(self):
        rows = (
            self.base_queryset()
            .values(
                "category__store__vertical__name",
                "category__store__vertical__slug",
            )
            .annotate(product_count=Count("id"))
            .order_by("category__store__vertical__name")
        )
        return [
            {
                "name": row["category__store__vertical__name"],
                "slug": row["category__store__vertical__slug"],
                "product_count": row["product_count"],
            }
            for row in rows
        ]

    def category_facets(self, vertical):
        products = self.base_queryset()
        if vertical:
            products = products.filter(
                category__store__vertical__slug=vertical
            )
        rows = (
            products
            .exclude(category__slug="")
            .values("category__name", "category__slug")
            .annotate(product_count=Count("id"))
            .order_by("category__name")
        )
        return [
            {
                "name": row["category__name"],
                "slug": row["category__slug"],
                "product_count": row["product_count"],
            }
            for row in rows
        ]

    @staticmethod
    def result_payload(product, request, filters):
        store = product.category.store
        availability = marketplace_store_availability(store)
        distance = None
        if filters["location"]:
            latitude, longitude = filters["location"]
            store_lat, store_lng = get_lat_lng(store, "latitude", "longitude")
            distance = RiderDispatcherService.haversine(
                longitude,
                latitude,
                float(store_lng),
                float(store_lat),
            )

        return {
            "id": str(product.id),
            "name": product.name,
            "description": product.description or "",
            "price": float(product.price),
            "image": product_image_url(product, request),
            "product_type": product.product_type,
            "unit_type": product.unit_type,
            "is_available": product.is_available,
            "availability_status": "AVAILABLE"
            if product.is_available and product.is_active
            else "UNAVAILABLE",
            "brand_name": product.brand_name or "",
            "generic_name": product.generic_name or "",
            "dosage": product.dosage or "",
            "requires_prescription": product.requires_prescription,
            "preparation_time_minutes": product.preparation_time_minutes,
            "modifier_groups": [
                {
                    "id": str(group.id),
                    "name": group.name,
                    "is_required": group.is_required,
                    "max_selections": group.items.filter(is_available=True).count(),
                    "items": [
                        {
                            "id": str(item.id),
                            "linked_product": str(item.linked_product_id) if item.linked_product_id else "",
                            "image_url": product_image_url(item.linked_product, request)
                            if item.linked_product_id
                            else "",
                            "name": item.name,
                            "extra_price": float(item.extra_price),
                            "is_available": item.is_available,
                        }
                        for item in group.items.all()
                    ],
                }
                for group in product.modifier_groups.all()
            ],
            "category": {
                "name": product.category.name,
                "slug": product.category.slug,
            },
            "store": {
                "id": str(store.id),
                "name": store.name,
                "vertical": {
                    "name": store.vertical.name,
                    "slug": store.vertical.slug,
                },
                "rating": float(store.rating),
                "is_open": availability["status"] == "OPEN",
                "availability_status": availability["status"],
                "availability_label": availability["status_label"],
                "availability_reason": availability["status_reason"],
                "barangay": store.barangay,
                "city": store.city,
            },
            "distance_km": round(distance, 2) if distance is not None else None,
        }


class PublicStoreListView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request):
        location, error = GlobalProductSearchView.parse_location(
            request.query_params.get("lat"),
            request.query_params.get("lng"),
        )
        if error:
            return error

        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(24, max(1, int(request.query_params.get("page_size", 12))))
        except (TypeError, ValueError):
            return Response({"error": "Pagination must use valid numbers."}, status=400)

        query = request.query_params.get("q", "").strip()[:120]
        vertical = request.query_params.get("vertical", "").strip()
        min_rating = request.query_params.get("min_rating")
        max_distance = request.query_params.get("max_distance")
        sort = request.query_params.get("sort", "recommended")
        if sort not in {"recommended", "fastest", "nearest", "rating", "name"}:
            return Response({"error": "Invalid sort option."}, status=400)
        if sort in {"fastest", "nearest"} and not location:
            sort = "recommended"
        try:
            min_rating = float(min_rating) if min_rating not in (None, "") else None
            max_distance = float(max_distance) if max_distance not in (None, "") else None
        except (TypeError, ValueError):
            return Response({"error": "Rating and distance must be valid numbers."}, status=400)
        if min_rating is not None and not 0 <= min_rating <= 5:
            return Response({"error": "Rating must be between 0 and 5."}, status=400)
        if max_distance is not None and max_distance <= 0:
            return Response({"error": "Distance must be greater than 0."}, status=400)
        if max_distance is not None and not location:
            return Response({"error": "Location is required for distance filtering."}, status=400)

        stores = self.store_queryset()
        if query:
            stores = stores.filter(
                Q(name__icontains=query)
                | Q(branch_name__icontains=query)
                | Q(city__icontains=query)
                | Q(barangay__icontains=query)
                | Q(categories__name__icontains=query)
            ).distinct()
        if vertical:
            stores = stores.filter(vertical__slug=vertical)
        if min_rating is not None:
            stores = stores.filter(rating__gte=min_rating)

        facets = self.vertical_facets()
        payload = [
            self.store_payload(store, request, location)
            for store in stores
        ]
        if max_distance is not None:
            payload = [
                store
                for store in payload
                if store["distance_km"] is not None
                and store["distance_km"] <= max_distance
            ]
        payload.sort(key=self.sort_key(sort))
        total_items = len(payload)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size

        return Response(
            {
                "results": payload[start:start + page_size],
                "facets": {"verticals": facets},
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1,
                },
            }
        )

    @staticmethod
    def store_queryset():
        available_products = Product.objects.filter(
            is_active=True,
            is_available=True,
        ).filter(Q(track_inventory=False) | Q(stock_quantity__gt=0))
        active_categories = Category.objects.filter(
            is_active=True,
            products__in=available_products,
        ).distinct()
        return (
            Store.objects.select_related("vertical")
            .filter(
                is_active=True,
                vertical__is_active=True,
                categories__in=active_categories,
            )
            .prefetch_related(
                Prefetch(
                    "categories",
                    queryset=active_categories.order_by("order", "name"),
                    to_attr="public_categories",
                )
            )
            .annotate(
                minimum_preparation_minutes=Min(
                    "categories__products__preparation_time_minutes",
                    filter=Q(
                        categories__products__is_active=True,
                        categories__products__is_available=True,
                    ),
                )
            )
            .distinct()
        )

    @classmethod
    def vertical_facets(cls):
        rows = (
            cls.store_queryset()
            .values("vertical__name", "vertical__slug")
            .annotate(store_count=Count("id", distinct=True))
            .order_by("vertical__name")
        )
        return [
            {
                "name": row["vertical__name"],
                "slug": row["vertical__slug"],
                "store_count": row["store_count"],
            }
            for row in rows
        ]

    @staticmethod
    def store_payload(store, request, location=None):
        distance = None
        delivery_eta_minutes = None
        delivery_fee = None
        if location:
            latitude, longitude = location
            store_lat, store_lng = get_lat_lng(store, "latitude", "longitude")
            distance = RiderDispatcherService.haversine(
                longitude,
                latitude,
                float(store_lng),
                float(store_lat),
            )
            travel_minutes, road_distance = RiderDispatcherService.calculate_eta(
                float(store_lat),
                float(store_lng),
                latitude,
                longitude,
            )
            delivery_eta_minutes = travel_minutes + (
                store.minimum_preparation_minutes or 0
            )
            delivery_fee = float(calculate_delivery_fee(road_distance))
        availability = marketplace_store_availability(store)
        is_open = availability["status"] == "OPEN"
        banner_image = ""
        if store.banner_image:
            try:
                banner_image = request.build_absolute_uri(store.banner_image.url)
            except ValueError:
                pass
        logo_image = ""
        if store.logo_image:
            try:
                logo_image = request.build_absolute_uri(store.logo_image.url)
            except ValueError:
                pass
        return {
            "id": str(store.id),
            "slug": store.slug,
            "name": store.name,
            "branch_name": store.branch_name or "",
            "banner_image": banner_image,
            "logo_image": logo_image,
            "vertical": {
                "name": store.vertical.name,
                "slug": store.vertical.slug,
            },
            "rating": float(store.rating),
            "is_open": is_open,
            "availability_status": availability["status"],
            "availability_label": availability["status_label"],
            "availability_reason": availability["status_reason"],
            "address": store.street_address,
            "barangay": store.barangay,
            "city": store.city,
            "distance_km": round(distance, 2) if distance is not None else None,
            "delivery_eta_minutes": delivery_eta_minutes,
            "delivery_fee": delivery_fee,
            "categories": [
                {"name": category.name, "slug": category.slug}
                for category in store.public_categories[:4]
            ],
        }

    @staticmethod
    def sort_key(sort):
        def key(store):
            open_rank = not store["is_open"]
            if sort == "nearest":
                return (
                    open_rank,
                    store["distance_km"] is None,
                    store["distance_km"] or 0,
                    store["name"],
                )
            if sort == "fastest":
                return (
                    open_rank,
                    store["delivery_eta_minutes"] is None,
                    store["delivery_eta_minutes"] or 0,
                    store["distance_km"] or 0,
                    store["name"],
                )
            if sort == "rating":
                return (open_rank, -store["rating"], store["name"])
            if sort == "name":
                return (open_rank, store["name"])
            return (open_rank, -store["rating"], store["name"])

        return key


def find_public_store(identifier):
    queryset = PublicStoreListView.store_queryset()
    store = queryset.filter(slug=identifier).first()
    if store:
        return store
    try:
        store_id = UUID(str(identifier))
    except (TypeError, ValueError):
        return None
    return queryset.filter(id=store_id).first()


class PublicStoreDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request, store_identifier):
        store = find_public_store(store_identifier)
        if not store:
            return Response({"error": "Store not found."}, status=404)
        location, error = GlobalProductSearchView.parse_location(
            request.query_params.get("lat"),
            request.query_params.get("lng"),
        )
        if error:
            return error
        return Response(PublicStoreListView.store_payload(store, request, location))


class PublicStoreDiscoveryView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request):
        location, error = GlobalProductSearchView.parse_location(
            request.query_params.get("lat"),
            request.query_params.get("lng"),
        )
        if error:
            return error
        try:
            limit = min(8, max(1, int(request.query_params.get("limit", 4))))
        except (TypeError, ValueError):
            return Response({"error": "Limit must be a valid number."}, status=400)

        stores = PublicStoreListView.store_queryset()
        groups = []
        for facet in PublicStoreListView.vertical_facets():
            payload = [
                PublicStoreListView.store_payload(store, request, location)
                for store in stores.filter(vertical__slug=facet["slug"])
            ]
            payload.sort(key=PublicStoreListView.sort_key("nearest" if location else "recommended"))
            groups.append(
                {
                    "vertical": {
                        "name": facet["name"],
                        "slug": facet["slug"],
                    },
                    "total_stores": facet["store_count"],
                    "stores": payload[:limit],
                }
            )
        return Response({"groups": groups})


class PublicStoreProductsView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request, store_identifier):
        store = find_public_store(store_identifier)
        if not store:
            return Response({"error": "Store not found."}, status=404)

        filters, error = GlobalProductSearchView().parse_filters(request)
        if error:
            return error
        store_products = Product.objects.select_related(
            "category",
            "category__store",
            "category__store__vertical",
        ).prefetch_related(
            Prefetch(
                "modifier_groups__items",
                queryset=ModifierItem.objects.select_related("linked_product"),
            ),
        ).filter(
            is_active=True,
            category__is_active=True,
            category__store_id=store.id,
            category__store__is_active=True,
            category__store__vertical__is_active=True,
        )
        products = store_products
        if filters["query"]:
            products = products.filter(
                Q(name__icontains=filters["query"])
                | Q(description__icontains=filters["query"])
                | Q(brand_name__icontains=filters["query"])
                | Q(generic_name__icontains=filters["query"])
            )
        if filters["category"]:
            products = products.filter(category__slug=filters["category"])
        if filters["min_price"] is not None:
            products = products.filter(price__gte=filters["min_price"])
        if filters["max_price"] is not None:
            products = products.filter(price__lte=filters["max_price"])
        availability_order = Case(
            When(
                Q(is_available=True)
                & (Q(track_inventory=False) | Q(stock_quantity__gt=0)),
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        )
        ordering = {
            "relevance": ("name", "price"),
            "price_low": ("price", "name"),
            "price_high": ("-price", "name"),
            "rating": ("name",),
            "nearest": ("name",),
        }
        products = products.order_by(
            availability_order,
            "category__order",
            *ordering[filters["sort"]],
        )
        total_items = products.count()
        start = (filters["page"] - 1) * filters["page_size"]
        end = start + filters["page_size"]
        results = [
            GlobalProductSearchView.result_payload(product, request, filters)
            for product in products[start:end]
        ]
        total_pages = max(
            1,
            (total_items + filters["page_size"] - 1) // filters["page_size"],
        )
        categories = (
            store_products.values(
                "category__name",
                "category__slug",
                "category__order",
            )
            .annotate(product_count=Count("id"))
            .order_by("category__order", "category__name")
        )
        return Response(
            {
                "results": results,
                "facets": {
                    "categories": [
                        {
                            "name": item["category__name"],
                            "slug": item["category__slug"],
                            "product_count": item["product_count"],
                        }
                        for item in categories
                    ]
                },
                "pagination": {
                    "page": filters["page"],
                    "page_size": filters["page_size"],
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": filters["page"] < total_pages,
                    "has_previous": filters["page"] > 1,
                },
            }
        )


class ProductComparisonView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "search"

    def get(self, request):
        product_id = request.query_params.get("product_id", "").strip()
        if not product_id:
            return Response({"error": "Product is required."}, status=400)

        location, error = GlobalProductSearchView.parse_location(
            request.query_params.get("lat"),
            request.query_params.get("lng"),
        )
        if error:
            return error

        products = GlobalProductSearchView.base_queryset()
        try:
            selected = products.filter(id=product_id).first()
        except ValidationError:
            return Response({"error": "Invalid product."}, status=400)
        if not selected:
            return Response({"error": "Product not found."}, status=404)

        matches = self.matching_products(products, selected)
        filters = {"location": location}
        options = [
            GlobalProductSearchView.result_payload(
                product,
                request,
                filters,
            )
            for product in matches
        ]
        options.sort(
            key=lambda item: (
                not item["store"]["is_open"],
                item["price"],
                item["distance_km"] is None,
                item["distance_km"] or 0,
            )
        )
        selected_option = next(
            item for item in options if item["id"] == str(selected.id)
        )
        lowest = min(options, key=lambda item: item["price"])

        return Response(
            {
                "selected_product_id": str(selected.id),
                "options": options,
                "summary": {
                    "alternative_count": max(len(options) - 1, 0),
                    "lowest_price_product_id": lowest["id"],
                    "potential_savings": max(
                        selected_option["price"] - lowest["price"],
                        0,
                    ),
                },
            }
        )

    @staticmethod
    def matching_products(products, selected):
        matches = products.filter(
            category__store__vertical_id=selected.category.store.vertical_id,
        )
        if selected.medicine_reference_id:
            return matches.filter(
                medicine_reference_id=selected.medicine_reference_id,
            )
        if selected.product_type.lower() == "medicine" and selected.generic_name:
            matches = matches.filter(
                generic_name__iexact=selected.generic_name,
            )
            if selected.dosage:
                matches = matches.filter(dosage__iexact=selected.dosage)
            return matches
        if selected.sku:
            return matches.filter(sku__iexact=selected.sku)
        return matches.filter(name__iexact=selected.name)
