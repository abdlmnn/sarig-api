from django.urls import path
from .views import ChatHistoryView

urlpatterns = [
    path("history/<uuid:order_id>/", ChatHistoryView.as_view(), name="chat-history"),
]
