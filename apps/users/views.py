from .serializers import (
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
