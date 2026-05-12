from rest_framework import generics, permissions
from .models import MerchantApplication, RiderApplication
from .serializers import MerchantApplicationSerializer, RiderApplicationSerializer


class MerchantApplicationCreateView(generics.CreateAPIView):
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MerchantApplication.objects.filter(applicant=self.request.user)


class MerchantApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MerchantApplication.objects.filter(applicant=self.request.user)


class RiderApplicationCreateView(generics.CreateAPIView):
    serializer_class = RiderApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RiderApplication.objects.filter(applicant=self.request.user)


class RiderApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = RiderApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RiderApplication.objects.filter(applicant=self.request.user)
