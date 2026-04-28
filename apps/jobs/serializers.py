from rest_framework import serializers

from apps.jobs.models import Application, Job, JobCategory


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ["id", "name"]


class JobSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    employer_id = serializers.IntegerField(source="employer.id", read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "employer_id",
            "category",
            "category_name",
            "title",
            "description",
            "requirements",
            "location_text",
            "salary_min",
            "salary_max",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "employer_id", "created_at", "updated_at"]


class ApplicationSerializer(serializers.ModelSerializer):
    seeker_id = serializers.IntegerField(source="seeker.id", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "seeker_id", "cover_letter", "status", "created_at"]
        read_only_fields = ["id", "seeker_id", "status", "created_at"]
