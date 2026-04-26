from .views import (
  UserProfileViewSet,
  BarangayViewSet,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(
  r'profiles',
  UserProfileViewSet,
  basename='profiles'
)
router.register(
  r'barangays',
  BarangayViewSet,
  basename='barangays'
)
