from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    """
    Allow:
    - Anyone (even unauthenticated) to read (safe methods),
    - Only authenticated owners to edit/delete.
    """

    def has_permission(self, request, view):
        # Allow all users to access safe methods (GET, HEAD, OPTIONS)
        if request.method in SAFE_METHODS:
            return True

        # For unsafe methods, user must be authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow read-only methods for everyone
        if request.method in SAFE_METHODS:
            return True

        # Only allow edit/delete if the user is the owner
        return obj.host == request.user


class IsHostOwnerOrReadOnly(BasePermission):
    """
    - Allow anyone to read (GET, HEAD, OPTIONS).
    - Allow only authenticated users with role='host' to create.
    - Allow only the owner to update or delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        # Only allow create if user is authenticated and a host
        if request.method == 'POST':
            return request.user.is_authenticated and getattr(request.user, 'role', None) == 'host'

        # Allow other unsafe methods only if authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.host == request.user


class IsBookingOwner(BasePermission):
    """
    Allow access only to the owner of the booking.
    """

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user