from .serializers import (
    AdminLoginSerializer,
    CustomerLoginSerializer,
    LoginSerializer,
    MerchantLoginSerializer,
    UserSerializer,
    ProfileSerializer,
    AddressSerializer,
    UserRegisterSerializer,
)
from .models import User, Profile, Address
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions

from .auth_sessions import (
    clear_refresh_cookie,
    cookie_name,
    rotate_refresh_token,
    revoke_user_refresh_tokens,
    set_refresh_cookie,
    validate_refresh_token,
)


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Admin sees all users
        if user.is_staff:
            return User.objects.all()

        # Regular users only see themselves
        return User.objects.filter(id=user.id)


class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Each user only accesses their own profile
        return Profile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically link profile to logged-in user
        serializer.save(user=self.request.user)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Each user only sees their own addresses
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign user
        serializer.save(user=self.request.user)


class MeViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["get", "patch"])
    def profile(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if request.method == "GET":
            return Response(ProfileSerializer(profile).data)

        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get", "post"])
    def addresses(self, request):
        if request.method == "GET":
            qs = Address.objects.filter(user=request.user)
            return Response(AddressSerializer(qs, many=True).data)

        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = []
    throttle_scope = "registration"


class ScopedLoginView(APIView):
    permission_classes = []
    serializer_class = None
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(self.format_login_errors(serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    def format_login_errors(self, errors):
        if "code" in errors and "message" in errors:
            return {
                "code": str(errors["code"][0]),
                "message": str(errors["message"][0]),
            }
        return errors


class LoginView(ScopedLoginView):
    serializer_class = LoginSerializer

    def post(self, request):
        if str(request.data.get("account_type", "")).upper() in {"ADMIN", "MERCHANT"}:
            return Response(
                {"detail": "Use the role-specific secure authentication endpoint."},
                status=status.HTTP_410_GONE,
            )
        return super().post(request)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfBootstrapView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        response = Response({"csrf_token": get_token(request)})
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(csrf_protect, name="dispatch")
class CookieScopedLoginView(ScopedLoginView):
    account_type = None

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(self.format_login_errors(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        payload = dict(serializer.validated_data)
        refresh = payload.pop("refresh")
        remember_me = payload.pop("remember_me", False)
        response = Response(payload, status=status.HTTP_200_OK)
        set_refresh_cookie(response, refresh, self.account_type, remember_me)
        response["Cache-Control"] = "no-store"
        return response


class AdminCookieLoginView(CookieScopedLoginView):
    account_type = "ADMIN"
    serializer_class = AdminLoginSerializer


class MerchantCookieLoginView(CookieScopedLoginView):
    account_type = "MERCHANT"
    serializer_class = MerchantLoginSerializer


class CustomerCookieLoginView(CookieScopedLoginView):
    account_type = "CUSTOMER"
    serializer_class = CustomerLoginSerializer


@method_decorator(csrf_protect, name="dispatch")
class CookieRefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"
    account_type = None

    def post(self, request):
        raw_token = request.COOKIES.get(cookie_name(self.account_type))
        if not raw_token:
            return Response({"detail": "Session is unavailable."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            access, refresh, user, remember_me = rotate_refresh_token(
                raw_token,
                self.account_type,
            )
        except (TokenError, APIException):
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                pass
            response = Response(
                {"detail": "Session is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            clear_refresh_cookie(response, self.account_type)
            return response

        response = Response(
            {
                "access": access,
                "account_type": self.account_type,
                "user": UserSerializer(user).data,
            }
        )
        set_refresh_cookie(response, refresh, self.account_type, remember_me)
        response["Cache-Control"] = "no-store"
        return response


class AdminCookieRefreshView(CookieRefreshView):
    account_type = "ADMIN"


class MerchantCookieRefreshView(CookieRefreshView):
    account_type = "MERCHANT"


class CustomerCookieRefreshView(CookieRefreshView):
    account_type = "CUSTOMER"


@method_decorator(csrf_protect, name="dispatch")
class CookieLogoutView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"
    account_type = None

    def post(self, request):
        raw_token = request.COOKIES.get(cookie_name(self.account_type))
        if raw_token:
            try:
                token, _ = validate_refresh_token(raw_token, self.account_type)
                token.blacklist()
            except TokenError:
                pass

        response = Response({"detail": "Logged out."})
        clear_refresh_cookie(response, self.account_type)
        response["Cache-Control"] = "no-store"
        return response


class AdminCookieLogoutView(CookieLogoutView):
    account_type = "ADMIN"


class MerchantCookieLogoutView(CookieLogoutView):
    account_type = "MERCHANT"


class CustomerCookieLogoutView(CookieLogoutView):
    account_type = "CUSTOMER"


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        revoke_user_refresh_tokens(request.user)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
