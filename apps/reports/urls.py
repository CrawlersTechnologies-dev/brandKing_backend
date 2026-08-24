from django.urls import path
from .views import RevenueReportView, GlobalDashboardView, SubAdminDashboardView, ExpenseViewSet, ExportReportView

urlpatterns = [
    path('revenue/', RevenueReportView.as_view(), name='revenue-report'),
    path('dashboard/', GlobalDashboardView.as_view(), name='global-dashboard'),
    path('subadmin-dashboard/', SubAdminDashboardView.as_view(), name='subadmin-dashboard'),
]

from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')

urlpatterns.extend(router.urls)
urlpatterns.append(path('export/', ExportReportView.as_view(), name='export-report'))
