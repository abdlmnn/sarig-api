from rest_framework import permissions, viewsets

from .models import EmailTemplate
from .serializers import EmailTemplateSerializer


class EmailTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = EmailTemplateSerializer
    permission_classes = [permissions.IsAdminUser]
    throttle_scope = "onboarding_status"

    def get_queryset(self):
        queryset = EmailTemplate.objects.all().order_by("key")
        is_active = self.request.query_params.get("is_active")

        if is_active in {"1", "true", "True"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"0", "false", "False"}:
            queryset = queryset.filter(is_active=False)

        return queryset
