from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Barangay, User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "verification_status", "barangay", "created_at")
    list_filter = ("role", "verification_status", "barangay")
    search_fields = ("user__username", "user__email", "phone_number")
    autocomplete_fields = ("user", "barangay")


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
