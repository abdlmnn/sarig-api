from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    CategoryTemplateViewSet,
    CategoryManagementDetailView,
    CategoryManagementListView,
    CategoryMoveView,
    CategoryReorderView,
    GlobalProductSearchView,
    MedicineReferenceViewSet,
    ProductComparisonView,
    ProductInventoryUpdateView,
    ProductManagementDetailView,
    ProductManagementListView,
    ProductViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"category-templates", CategoryTemplateViewSet, basename="category-templates")
router.register(r"products", ProductViewSet)
router.register(r"medicine-references", MedicineReferenceViewSet, basename="medicine-references")

urlpatterns = [
    path("categories/manage/", CategoryManagementListView.as_view(), name="catalog-category-management"),
    path("categories/manage/reorder/", CategoryReorderView.as_view(), name="catalog-category-reorder"),
    path("categories/manage/<uuid:category_id>/", CategoryManagementDetailView.as_view(), name="catalog-category-management-detail"),
    path("categories/manage/<uuid:category_id>/move/", CategoryMoveView.as_view(), name="catalog-category-move"),
    path("products/manage/", ProductManagementListView.as_view(), name="catalog-product-management"),
    path("products/manage/<uuid:product_id>/inventory/", ProductInventoryUpdateView.as_view(), name="catalog-product-inventory"),
    path("products/manage/<uuid:product_id>/", ProductManagementDetailView.as_view(), name="catalog-product-management-detail"),
    path("search/", GlobalProductSearchView.as_view(), name="global-search"),
    path("compare/", ProductComparisonView.as_view(), name="product-compare"),
    path("", include(router.urls)),
]
