from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet, DatabaseBackupView

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('backup/', DatabaseBackupView.as_view(), name='database-backup'),
    path('', include(router.urls)),
]
