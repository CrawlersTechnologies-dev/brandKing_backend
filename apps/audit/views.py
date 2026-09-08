from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import AuditLog
from .serializers import AuditLogSerializer
from common.permissions import IsSubAdmin

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsSubAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['module', 'action', 'object_type', 'object_id', 'user', 'branch', 'role']
    search_fields = ['old_value', 'new_value', 'object_type']

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.all().order_by('-timestamp')
        
        # Sub-admins can only see audit logs for their branch
        from common.constants import ROLE_SUB_ADMIN
        if user.role == ROLE_SUB_ADMIN:
            qs = qs.filter(branch=user.branch)
            
        return qs

import io
from django.core.management import call_command
from django.http import HttpResponse
from rest_framework.views import APIView
from common.permissions import IsGlobalAdmin
from django.utils import timezone
from common.responses import error_response

class DatabaseBackupView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsGlobalAdmin]

    def get(self, request):
        try:
            output = io.StringIO()
            # Exclude specific tables that shouldn't be backed up or cause issues during restore
            call_command('dumpdata', exclude=['contenttypes', 'auth.permission', 'sessions'], stdout=output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/json')
            filename = f"db_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return error_response(message=f"Backup failed: {str(e)}", status=500)
