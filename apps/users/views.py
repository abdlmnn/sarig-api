from .serializers import (
    LoginSerializer,
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
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken, TokenError


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


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            raise ValidationError({"refresh": "This field is required."})
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
