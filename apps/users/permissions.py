from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    role_name = None

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.is_staff:
            return True

        return user.roles.filter(name=self.role_name).exists()


class IsCustomer(HasRole):
    role_name = "customer"


class IsMerchant(HasRole):
    role_name = "merchant"


class IsRider(HasRole):
    role_name = "rider"
