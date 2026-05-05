from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, GlobalProductSearchView, ProductComparisonView

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("search/", GlobalProductSearchView.as_view(), name="global-search"),
    path("compare/", ProductComparisonView.as_view(), name="product-compare"),
]
