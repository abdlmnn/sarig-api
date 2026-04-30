from rest_framework.routers import DefaultRouter

from apps.jobs.views import ApplicationViewSet, JobCategoryViewSet, JobViewSet

router = DefaultRouter()

router.register(
  r"categories",
  JobCategoryViewSet,
  basename="job-category"
)
router.register(
  r"postings",
  JobViewSet,
  basename="job-posting"
)
router.register(
  r"applications",
  ApplicationViewSet,
  basename="job-application"
)
