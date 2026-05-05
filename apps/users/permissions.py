from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    role_name = None

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        # Check for both Title Case and lowercase for robustness
        return user.roles.filter(name__iexact=self.role_name).exists()


class IsCustomer(HasRole):
    role_name = "Customer"


class IsMerchant(HasRole):
    role_name = "Merchant"


class IsRider(HasRole):
    role_name = "Rider"


class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
            
        # Check if object has an 'owner' or 'user' attribute
        owner = getattr(obj, 'owner', getattr(obj, 'user', None))
        return owner == request.user
