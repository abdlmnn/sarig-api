from django.urls import path, include
from .views import (
  RegisterView,
  MeView,
  LogoutView,
)
from rest_framework_simplejwt.views import (
  TokenObtainPairView,
  TokenRefreshView,
)
from .routers import router

urlpatterns = [
  path(
    "register/",
    RegisterView.as_view(),
    name="register"
  ),
  path(
    "login/",
    TokenObtainPairView.as_view(),
    name="token_obtain_pair"
  ),
  path(
    "logout/",
    LogoutView.as_view(),
    name="logout"
  ),
  path(
    "token/refresh/",
    TokenRefreshView.as_view(),
    name="token_refresh"
  ),
  path(
    "me/",
    MeView.as_view(),
    name="me"
  ),
  path(
    "",
    include(router.urls)
  ),
]

