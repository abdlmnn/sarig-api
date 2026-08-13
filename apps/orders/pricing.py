from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import ModifierGroup, ModifierItem, Product
from apps.locations import services as location_services
from apps.marketing.models import PromoCode
from apps.vendors.utils import PH_TZ, store_availability_payload

from .models import DeliveryMethod, DeliveryOption


class CheckoutPricingError(Exception):
    pass


@dataclass
class CheckoutPricing:
    subtotal: Decimal
    delivery_fee: Decimal
    system_fee: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    distance_km: Decimal | None
    estimated_minutes: int | None
    delivery_options: list[dict]
    promo: PromoCode | None
    order_items: list[dict]
    requires_prescription: bool
    prescription_product_name: str | None

    def quote_payload(self):
        return {
            "subtotal": str(self.subtotal),
            "delivery_fee": str(self.delivery_fee),
            "service_fee": str(self.system_fee),
            "discount_amount": str(self.discount_amount),
            "total_amount": str(self.total_amount),
            "distance_km": str(self.distance_km) if self.distance_km is not None else None,
            "estimated_minutes": self.estimated_minutes,
            "delivery_options": self.delivery_options,
        }


def calculate_checkout_pricing(store, data, *, lock_products=False):
    availability = store_availability_payload(
        store,
        timezone.now().astimezone(PH_TZ),
    )
    if not store.is_active or availability["status"] != "OPEN":
        raise CheckoutPricingError("This store is currently closed or inactive.")

    product_queryset = Product.objects.select_related("category")
    if lock_products:
        product_queryset = product_queryset.select_for_update()

    subtotal = Decimal("0.00")
    order_items = []
    requires_prescription = False
    prescription_product_name = None
    preparation_minutes = 0

    for item_data in data["items"]:
        product = product_queryset.filter(id=item_data["product_id"]).first()
        if not product:
            raise CheckoutPricingError("One or more products no longer exist.")
        if product.category.store_id != store.id:
            raise CheckoutPricingError(
                f"Product {product.name} does not belong to this store."
            )
        if not product.in_stock:
            raise CheckoutPricingError(
                f"Product {product.name} is currently unavailable."
            )

        quantity = item_data["quantity"]
        if (
            product.track_inventory
            and product.stock_quantity is not None
            and product.stock_quantity < quantity
        ):
            raise CheckoutPricingError(f"Insufficient stock for {product.name}.")

        modifiers = _selected_modifiers(product, item_data.get("modifier_item_ids", []))
        modifier_error = _validate_modifiers(product, modifiers)
        if modifier_error:
            raise CheckoutPricingError(modifier_error)

        modifier_total = sum(
            (modifier.extra_price for modifier in modifiers),
            Decimal("0.00"),
        )
        unit_price = product.price + modifier_total
        subtotal += unit_price * quantity
        preparation_minutes = max(
            preparation_minutes,
            product.preparation_time_minutes
            or settings.ORDER_DEFAULT_PREPARATION_MINUTES,
        )
        if product.requires_prescription:
            requires_prescription = True
            prescription_product_name = prescription_product_name or product.name
        modifier_note = ", ".join(
            f"{modifier.group.name}: {modifier.name}" for modifier in modifiers
        )
        instructions = item_data.get("special_instructions", "")
        if modifier_note:
            instructions = f"{modifier_note}\n{instructions}".strip()
        order_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "special_instructions": instructions,
            }
        )

    delivery_fee = Decimal("0.00")
    delivery_options = []
    distance_km = None
    travel_minutes = 0
    if data["delivery_method"] == DeliveryMethod.DELIVERY:
        estimate = location_services.route_estimate(
            {"latitude": store.latitude, "longitude": store.longitude},
            {"latitude": data["latitude"], "longitude": data["longitude"]},
        )
        distance_km = Decimal(str(estimate["distance_km"]))
        if float(distance_km) > settings.DELIVERY_MAX_DISTANCE_KM:
            raise CheckoutPricingError(
                "Delivery address is outside the supported distance."
            )
        base_delivery_fee = location_services.calculate_delivery_fee(distance_km)
        delivery_fee = delivery_option_fee(
            base_delivery_fee,
            data.get("delivery_option", DeliveryOption.STANDARD),
        )
        travel_minutes = delivery_option_minutes(
            int(estimate["duration_minutes"]),
            data.get("delivery_option", DeliveryOption.STANDARD),
        )
        delivery_options = delivery_option_payloads(
            base_delivery_fee,
            int(estimate["duration_minutes"]),
            preparation_minutes,
        )

    promo = None
    discount_amount = Decimal("0.00")
    promo_code = data.get("promo_code")
    if promo_code:
        promo = PromoCode.objects.filter(code__iexact=promo_code).first()
        if not promo:
            raise CheckoutPricingError("Invalid promo code.")
        is_valid, error_message = promo.is_valid(subtotal)
        if not is_valid:
            raise CheckoutPricingError(error_message)
        discount_amount = promo.calculate_discount(subtotal)

    system_fee = Decimal(str(settings.ORDER_SYSTEM_FEE))
    total_amount = max(
        subtotal + delivery_fee + system_fee - discount_amount,
        Decimal("0.00"),
    )
    estimated_minutes = preparation_minutes + travel_minutes

    return CheckoutPricing(
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        system_fee=system_fee,
        discount_amount=discount_amount,
        total_amount=total_amount,
        distance_km=distance_km,
        estimated_minutes=estimated_minutes,
        delivery_options=delivery_options,
        promo=promo,
        order_items=order_items,
        requires_prescription=requires_prescription,
        prescription_product_name=prescription_product_name,
    )


def _selected_modifiers(product, modifier_ids):
    if not modifier_ids:
        return []
    modifiers = list(
        ModifierItem.objects.select_related("group").filter(
            id__in=modifier_ids,
            group__product=product,
            is_available=True,
        )
    )
    if len(modifiers) != len(set(modifier_ids)):
        raise CheckoutPricingError(
            f"Invalid modifier selected for {product.name}."
        )
    return modifiers


def _validate_modifiers(product, selected_modifiers):
    selected_by_group = {}
    for modifier in selected_modifiers:
        selected_by_group.setdefault(modifier.group_id, []).append(modifier)

    for group in ModifierGroup.objects.filter(product=product):
        selected = selected_by_group.get(group.id, [])
        if group.is_required and not selected:
            return f"{group.name} is required for {product.name}."
        if len(selected) > modifier_group_limit(group):
            return (
                f"Select up to {modifier_group_limit(group)} option(s) "
                f"for {group.name}."
            )
    return ""


def delivery_option_fee(base_fee, option):
    multipliers = {
        DeliveryOption.SAVER: Decimal(str(settings.DELIVERY_SAVER_FEE_MULTIPLIER)),
        DeliveryOption.STANDARD: Decimal("1.00"),
        DeliveryOption.PRIORITY: Decimal(str(settings.DELIVERY_PRIORITY_FEE_MULTIPLIER)),
    }
    fee = base_fee * multipliers.get(option, Decimal("1.00"))
    return fee.quantize(Decimal("0.01"))


def delivery_option_minutes(base_minutes, option):
    adjustments = {
        DeliveryOption.SAVER: int(settings.DELIVERY_SAVER_EXTRA_MINUTES),
        DeliveryOption.STANDARD: 0,
        DeliveryOption.PRIORITY: -int(settings.DELIVERY_PRIORITY_REDUCED_MINUTES),
    }
    return max(1, base_minutes + adjustments.get(option, 0))


def delivery_option_payloads(base_fee, base_minutes, preparation_minutes):
    options = [
        (DeliveryOption.SAVER, "Saver"),
        (DeliveryOption.STANDARD, "Standard"),
        (DeliveryOption.PRIORITY, "Priority"),
    ]
    return [
        {
            "value": option,
            "label": label,
            "delivery_fee": str(delivery_option_fee(base_fee, option)),
            "estimated_minutes": preparation_minutes
            + delivery_option_minutes(base_minutes, option),
        }
        for option, label in options
    ]


def modifier_group_limit(group):
    if group.is_required:
        return group.max_selections
    return max(group.max_selections, group.items.filter(is_available=True).count())
