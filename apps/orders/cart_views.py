from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import ModifierGroup, ModifierItem, Product
from apps.users.permissions import IsCustomer

from .cart_serializers import (
    CartItemMutationSerializer,
    CartSyncSerializer,
    CustomerCartSerializer,
)
from .models import CustomerCart, CustomerCartItem


def customer_carts(user):
    return (
        CustomerCart.objects.filter(customer=user)
        .select_related("store__vertical")
        .prefetch_related(
            "items__product",
            "items__modifiers__group",
        )
    )


def serialize_carts(request):
    return CustomerCartSerializer(
        customer_carts(request.user),
        many=True,
        context={"request": request},
    ).data


class CustomerCartListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get(self, request):
        return Response(serialize_carts(request))


class CustomerCartItemView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    @transaction.atomic
    def put(self, request, product_id):
        serializer = CartItemMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(
            Product.objects.select_related("category__store"),
            id=product_id,
        )
        error = product_cart_error(product)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = CustomerCart.objects.get_or_create(
            customer=request.user,
            store=product.category.store,
        )
        cart_item, _ = CustomerCartItem.objects.update_or_create(
            cart=cart,
            line_key=str(product.id),
            defaults={
                "product": product,
                **serializer.validated_data,
            },
        )
        cart_item.modifiers.clear()
        cart.save(update_fields=["updated_at"])
        return Response(serialize_carts(request))

    @transaction.atomic
    def delete(self, request, product_id):
        CustomerCartItem.objects.filter(
            cart__customer=request.user,
            line_key=str(product_id),
        ).delete()
        CustomerCart.objects.filter(customer=request.user, items__isnull=True).delete()
        return Response(serialize_carts(request))


class CustomerStoreCartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def delete(self, request, store_id):
        CustomerCart.objects.filter(
            customer=request.user,
            store_id=store_id,
        ).delete()
        return Response(serialize_carts(request))


class CustomerCartSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    @transaction.atomic
    def post(self, request):
        serializer = CartSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        baskets = serializer.validated_data["baskets"]
        replace = serializer.validated_data["mode"] == "REPLACE"
        validated_baskets = []
        for basket in baskets:
            products = {
                product.id: product
                for product in Product.objects.select_related(
                    "category__store",
                ).prefetch_related("modifier_groups__items").filter(
                    id__in=[item["product_id"] for item in basket["items"]]
                )
            }
            product_ids = {item["product_id"] for item in basket["items"]}
            if len(products) != len(product_ids):
                return Response(
                    {"detail": "One or more products no longer exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if any(
                product.category.store_id != basket["store_id"]
                for product in products.values()
            ):
                return Response(
                    {"detail": "A product does not belong to its selected store."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated_baskets.append((basket, products))

        if replace:
            CustomerCart.objects.filter(customer=request.user).exclude(
                store_id__in=[basket["store_id"] for basket in baskets]
            ).delete()

        for basket, products in validated_baskets:
            cart = CustomerCart.objects.filter(
                customer=request.user,
                store_id=basket["store_id"],
            ).first()
            if replace and cart:
                cart.items.exclude(
                    line_key__in=[
                        cart_line_key(
                            item["product_id"],
                            item.get("modifier_item_ids", []),
                        )
                        for item in basket["items"]
                    ]
                ).delete()
            for item in basket["items"]:
                product = products[item["product_id"]]
                modifiers, error = selected_cart_modifiers(
                    product,
                    item.get("modifier_item_ids", []),
                )
                if error:
                    return Response(
                        {"detail": error},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not cart:
                    cart = CustomerCart.objects.create(
                        customer=request.user,
                        store_id=basket["store_id"],
                    )
                line_key = cart_line_key(
                    product.id,
                    [modifier.id for modifier in modifiers],
                )
                existing = CustomerCartItem.objects.filter(
                    cart=cart,
                    line_key=line_key,
                ).first()
                quantity = (
                    item["quantity"]
                    if replace
                    else max(existing.quantity if existing else 0, item["quantity"])
                )
                cart_item, _ = CustomerCartItem.objects.update_or_create(
                    cart=cart,
                    line_key=line_key,
                    defaults={
                        "product": product,
                        "quantity": quantity,
                        "special_instructions": item.get(
                            "special_instructions",
                            "",
                        ),
                    },
                )
                cart_item.modifiers.set(modifiers)
            if cart:
                cart.save(update_fields=["updated_at"])

        return Response(serialize_carts(request))


def product_cart_error(product):
    store = product.category.store
    if not store.is_active or not store.is_open:
        return "This store is currently closed."
    if not product.in_stock:
        return "This product is currently unavailable."
    if product.requires_prescription:
        return "This product requires a prescription."
    return ""


def cart_line_key(product_id, modifier_ids):
    modifiers = sorted(str(modifier_id) for modifier_id in modifier_ids)
    return f"{product_id}:{':'.join(modifiers)}" if modifiers else str(product_id)


def selected_cart_modifiers(product, modifier_ids):
    if not modifier_ids:
        return [], validate_cart_modifiers(product, [])

    modifiers = list(
        ModifierItem.objects.select_related("group").filter(
            id__in=modifier_ids,
            group__product=product,
            is_available=True,
        )
    )
    if len(modifiers) != len(set(modifier_ids)):
        return [], f"Invalid modifier selected for {product.name}."
    error = validate_cart_modifiers(product, modifiers)
    return modifiers, error


def validate_cart_modifiers(product, selected_modifiers):
    selected_by_group = {}
    for modifier in selected_modifiers:
        selected_by_group.setdefault(modifier.group_id, []).append(modifier)

    for group in ModifierGroup.objects.filter(product=product):
        selected = selected_by_group.get(group.id, [])
        if group.is_required and not selected:
            return f"{group.name} is required for {product.name}."
        if len(selected) > group.max_selections:
            return (
                f"Select up to {group.max_selections} option(s) "
                f"for {group.name}."
            )
    return ""
