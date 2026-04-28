from django.db.models import Q
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.jobs.models import Application, Job, JobCategory
from apps.jobs.permissions import IsEmployer, IsSeeker
from apps.jobs.serializers import (
    ApplicationSerializer,
    JobCategorySerializer,
    JobSerializer,
)


class JobCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobCategory.objects.all().order_by("name")
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.AllowAny]


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.select_related("employer", "category").all()
    serializer_class = JobSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        status_val = self.request.query_params.get("status")
        is_active = self.request.query_params.get("is_active")
        location = self.request.query_params.get("location")
        search = self.request.query_params.get("search")

        if category:
            qs = qs.filter(category_id=category)
        if status_val is not None:
            qs = qs.filter(status=status_val)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in {"1", "true", "yes", "on"})
        if location:
            qs = qs.filter(location_text__icontains=location)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
        return qs

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsEmployer()]
        if self.action == "apply":
            return [IsSeeker()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user.profile)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        job = self.get_object()
        seeker = request.user.profile
        serializer = ApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            app = Application.objects.create(
                job=job,
                seeker=seeker,
                cover_letter=serializer.validated_data.get("cover_letter", ""),
            )
        except Exception:
            raise serializers.ValidationError("You already applied for this job.")
        return Response(ApplicationSerializer(app).data, status=status.HTTP_201_CREATED)


class ApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = self.request.user.profile
        role = profile.role
        if role == 1:  # seeker
            return Application.objects.filter(seeker=profile).select_related("job", "seeker")
        return Application.objects.filter(job__employer=profile).select_related("job", "seeker")

    @action(detail=True, methods=["patch"], permission_classes=[IsEmployer])
    def set_status(self, request, pk=None):
        app = self.get_object()
        if app.job.employer_id != request.user.profile.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        try:
            new_status = int(request.data.get("status"))
        except (TypeError, ValueError):
            return Response({"detail": "status must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = {choice[0] for choice in Application.Status.choices}
        if new_status not in valid_statuses:
            return Response({"detail": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        app.status = new_status
        app.save(update_fields=["status"])
        return Response(ApplicationSerializer(app).data, status=status.HTTP_200_OK)
