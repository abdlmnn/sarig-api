from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    GlobalProductSearchView,
    MedicineReferenceViewSet,
    ProductComparisonView,
    ProductManagementDetailView,
    ProductManagementListView,
    ProductViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)
router.register(r"medicine-references", MedicineReferenceViewSet, basename="medicine-references")

urlpatterns = [
    path("products/manage/", ProductManagementListView.as_view(), name="catalog-product-management"),
    path("products/manage/<uuid:product_id>/", ProductManagementDetailView.as_view(), name="catalog-product-management-detail"),
    path("search/", GlobalProductSearchView.as_view(), name="global-search"),
    path("compare/", ProductComparisonView.as_view(), name="product-compare"),
    path("", include(router.urls)),
]
