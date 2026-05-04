from rest_framework.permissions import BasePermission


class IsMerchantOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.is_staff:
            return True

        return user.roles.filter(name="merchant").exists()
