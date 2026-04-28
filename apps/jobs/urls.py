from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.jobs.views import ApplicationViewSet, JobCategoryViewSet, JobViewSet

router = DefaultRouter()
router.register("categories", JobCategoryViewSet, basename="job-category")
router.register("postings", JobViewSet, basename="job-posting")
router.register("applications", ApplicationViewSet, basename="job-application")

urlpatterns = [
    path("", include(router.urls)),
]
