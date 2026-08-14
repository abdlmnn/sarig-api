from decimal import Decimal, ROUND_HALF_UP


def money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money_payload(value):
    value = money(value)
    return {
        "value": str(value),
        "currency": "PHP",
        "formatted": f"₱{value:,.0f}",
    }