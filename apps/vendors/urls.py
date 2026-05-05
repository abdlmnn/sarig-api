from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StoreViewSet, BusinessVerticalViewSet

router = DefaultRouter()

router.register(r"stores", StoreViewSet, basename="stores")
router.register(r"verticals", BusinessVerticalViewSet, basename="verticals")

urlpatterns = [
    path("", include(router.urls)),
]
