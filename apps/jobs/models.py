from django.db import models

from apps.users.models import UserProfile


class JobCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Job(models.Model):
    class Status(models.IntegerChoices):
        DRAFT = 0, "Draft"
        OPEN = 1, "Open"
        CLOSED = 2, "Closed"

    employer = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="jobs"
    )
    category = models.ForeignKey(
        JobCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    location_text = models.CharField(max_length=180, default="Marawi City")
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "is_active"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["location_text"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Application(models.Model):
    class Status(models.IntegerChoices):
        PENDING = 0, "Pending"
        REVIEWED = 1, "Reviewed"
        SHORTLISTED = 2, "Shortlisted"
        HIRED = 3, "Hired"
        REJECTED = 4, "Rejected"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    seeker = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="job_applications"
    )
    cover_letter = models.TextField(blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("job", "seeker")
        indexes = [models.Index(fields=["status", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seeker_id} -> {self.job_id}"
