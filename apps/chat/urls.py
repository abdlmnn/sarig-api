from django.urls import path
from .views import ChatHistoryView, RideChatHistoryView

urlpatterns = [
    path("history/<uuid:order_id>/", ChatHistoryView.as_view(), name="chat-history"),
    path("ride-history/<uuid:ride_id>/", RideChatHistoryView.as_view(), name="ride-chat-history"),
]
