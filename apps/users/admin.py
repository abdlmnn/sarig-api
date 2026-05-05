from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User, Profile, Address


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Roles",
            {"fields": ("roles", "phone_number")},
        ),
    )

    filter_horizontal = ("roles",)  # important for ManyToMany UI

    list_display = (
        "username",
        "email",
        "phone_number",
        "get_roles",
        "is_staff",
    )

    search_fields = ("username", "email", "phone_number")

    def get_roles(self, obj):
        return ", ".join([r.name for r in obj.roles.all()])

    get_roles.short_description = "Roles"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "date_of_birth")
    search_fields = ("user__username", "user__email")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "is_default")
    search_fields = ("user__username", "label")
    list_filter = ("is_default",)
