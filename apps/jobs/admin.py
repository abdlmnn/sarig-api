from django.contrib import admin

from apps.jobs.models import Application, Job, JobCategory


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "employer",
        "category",
        "location_text",
        "status",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active", "category", "location_text", "created_at")
    search_fields = ("title", "description", "requirements", "location_text")
    autocomplete_fields = ("employer", "category")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "seeker", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("job__title", "seeker__user__username", "cover_letter")
    autocomplete_fields = ("job", "seeker")
    readonly_fields = ("created_at",)
