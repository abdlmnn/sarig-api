from rest_framework.routers import DefaultRouter

from .views import RideViewSet

router = DefaultRouter()
router.register("", RideViewSet, basename="rides")

urlpatterns = router.urls

