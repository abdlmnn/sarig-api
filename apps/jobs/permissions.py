from rest_framework import permissions
from apps.users.models import Role

class IsEmployer(permissions.BasePermission):
  def has_permission(self, request, view):
    if not request.user.is_authenticated:
      return False
    profile = getattr(request.user, "profile", None)
    return bool(profile and profile.role in {Role.EMPLOYER, Role.ADMIN})

class IsSeeker(permissions.BasePermission):
  def has_permission(self, request, view):
    if not request.user.is_authenticated:
      return False
    profile = getattr(request.user, "profile", None)
    return bool(profile and profile.role == Role.SEEKER)
