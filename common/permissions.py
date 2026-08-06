from rest_framework.permissions import BasePermission
from common.constants import ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_EMPLOYEE

class IsGlobalAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ROLE_ADMIN)

class IsSubAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in [ROLE_ADMIN, ROLE_SUB_ADMIN])

class IsBranchEmployee(BasePermission):
    def has_permission(self, request, view):
        # We allow Admin, Sub-Admin, and Employee to act as an employee for their branch (except Admin who has all branches)
        return bool(request.user and request.user.is_authenticated)
