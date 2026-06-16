from django.contrib import admin
from django.urls import path, include

from rest_framework.views import APIView
from rest_framework.response import Response


class testView(APIView):
    def get(self, request):
        return Response({"message": "It's working meeeeeeeeeeeeeen....."})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.v1.urls", namespace="v1")),
    path("test/", testView.as_view(), name="test"),
]
