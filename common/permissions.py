from rest_framework.permissions import BasePermission
from common.constants import ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_CASHIER, ROLE_STORE_STAFF

class IsGlobalAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ROLE_ADMIN)

class IsSubAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in [ROLE_ADMIN, ROLE_SUB_ADMIN])

class IsCashier(BasePermission):
    def has_permission(self, request, view):
        # Admins, Sub-Admins, Cashiers, and Store Staff can access billing
        return bool(request.user and request.user.is_authenticated and request.user.role in [ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_CASHIER, ROLE_STORE_STAFF])

class IsStoreStaff(BasePermission):
    def has_permission(self, request, view):
        # Admins, Sub-Admins, Store Staff, and Cashiers can access inventory/products
        return bool(request.user and request.user.is_authenticated and request.user.role in [ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_STORE_STAFF, ROLE_CASHIER])

class IsBranchStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in [ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_CASHIER, ROLE_STORE_STAFF])
