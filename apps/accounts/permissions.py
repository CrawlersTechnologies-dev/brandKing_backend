from rest_framework.permissions import BasePermission
from common.constants import ROLE_ADMIN, ROLE_SUB_ADMIN

class IsDocumentOwnerOrAdminOrSubAdmin(BasePermission):
    """
    Global Admin: All access.
    Sub-Admin: Access to documents of employees in their own branch.
    Employee: Access to their own documents.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin has all access
        if user.role == ROLE_ADMIN:
            return True
            
        # If it's a UserDocument, the target is obj.user.
        # If it's a User, the target is obj.
        target_user = getattr(obj, 'user', obj)

        # Sub-Admin has access if the target is in the same branch
        if user.role == ROLE_SUB_ADMIN:
            return bool(user.branch_id and target_user.branch_id == user.branch_id)
            
        # Employee has access only if they are the target user
        return target_user.id == user.id
