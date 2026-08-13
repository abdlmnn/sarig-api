from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsCustomer

from .models import PromoCode
from .serializers import AvailablePromoCodeSerializer


class AvailablePromoCodeListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get(self, request):
        subtotal = parse_subtotal(request.query_params.get("subtotal"))
        now = timezone.now()
        promos = PromoCode.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
            min_order_amount__lte=subtotal,
        ).order_by("-created_at")
        promos = [
            promo
            for promo in promos
            if not promo.usage_limit or promo.usage_count < promo.usage_limit
        ]
        return Response(AvailablePromoCodeSerializer(promos, many=True).data)


def parse_subtotal(value):
    try:
        subtotal = Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")
    return max(subtotal, Decimal("0.00"))
