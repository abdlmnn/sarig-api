from django.contrib import admin
from django.conf import settings
from django.urls import path, include

urlpatterns = [
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path("api/v1/", include("apps.v1.urls", namespace="v1")),
]
