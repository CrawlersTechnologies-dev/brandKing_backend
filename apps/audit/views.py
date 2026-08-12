from rest_framework import viewsets, permissions
from .models import AuditLog
from .serializers import AuditLogSerializer
from common.permissions import IsSubAdmin

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsSubAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.all().order_by('-timestamp')
        
        # Sub-admins can only see audit logs for their branch
        from common.constants import ROLE_SUB_ADMIN
        if user.role == ROLE_SUB_ADMIN:
            qs = qs.filter(branch=user.branch)
            
        # Optional filters
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
            
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
            
        return qs
