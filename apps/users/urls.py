from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    ProfileViewSet,
    AddressViewSet,
    MeViewSet,
    RegisterView,
)

router = DefaultRouter()

router.register(r"", UserViewSet, basename="user")
router.register(r"profiles", ProfileViewSet, basename="profile")
router.register(r"addresses", AddressViewSet, basename="address")
router.register(r"me", MeViewSet, basename="me")


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("", include(router.urls)),
]
