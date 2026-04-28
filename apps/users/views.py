from rest_framework import (
  generics,
  permissions,
  viewsets
)
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from .serializers import (
  UserRegisterSerializer,
  UserSerializer,
  BarangaySerializer,
  UserProfileSerializer,
)
from .models import (
  User,
  Barangay,
  UserProfile
)
from .permissions import IsOwnerOrReadOnly

class RegisterView(generics.CreateAPIView):
  queryset = User.objects.all()
  serializer_class = UserRegisterSerializer
  permission_classes = [permissions.AllowAny]

class MeView(generics.RetrieveAPIView):
  serializer_class = UserSerializer
  permission_classes = [permissions.IsAuthenticated]

  def get_object(self):
    return self.request.user

class UserProfileViewSet(viewsets.ModelViewSet):
  queryset = UserProfile.objects.select_related('user', 'barangay')
  serializer_class = UserProfileSerializer
  permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

  def get_queryset(self):
    qs = super().get_queryset()

    role = self.request.query_params.get('role')
    barangay = self.request.query_params.get('barangay')
    verification = self.request.query_params.get('verification_status')

    if role:
      qs = qs.filter(role=role)

    if barangay:
      qs = qs.filter(barangay_id=barangay)

    if verification:
      qs = qs.filter(verification_status=verification)

    return qs

  def perform_create(self, serializer):
    if hasattr(self.request.user, 'profile'):
      raise serializers.ValidationError('Profile already exists.')
    serializer.save(user=self.request.user)

  @action(
    detail=False,
    methods=['get'],
    permission_classes=[permissions.IsAuthenticated]
  )
  def me(self, request):
    try:
      profile = request.user.profile
    except UserProfile.DoesNotExist:
      raise NotFound('User profile does not exist.')
    serializer = self.get_serializer(profile)
    return Response(serializer.data)

class BarangayViewSet(viewsets.ReadOnlyModelViewSet):
  queryset = Barangay.objects.all()
  serializer_class = BarangaySerializer
  permission_classes = [permissions.AllowAny]
