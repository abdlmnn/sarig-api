from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmailTemplateViewSet

router = DefaultRouter()
router.register("templates", EmailTemplateViewSet, basename="email-template")

urlpatterns = [
    path("", include(router.urls)),
]
