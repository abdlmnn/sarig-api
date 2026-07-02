from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, MedicineReferenceViewSet, ProductViewSet, GlobalProductSearchView, ProductComparisonView

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)
router.register(r"medicine-references", MedicineReferenceViewSet, basename="medicine-references")

urlpatterns = [
    path("", include(router.urls)),
    path("search/", GlobalProductSearchView.as_view(), name="global-search"),
    path("compare/", ProductComparisonView.as_view(), name="product-compare"),
]
