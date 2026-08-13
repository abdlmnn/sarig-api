from django.urls import path

from .views import AvailablePromoCodeListView

urlpatterns = [
    path("promos/available/", AvailablePromoCodeListView.as_view(), name="available-promos"),
]
