from django.urls import path
from .views import RevenueReportView, GlobalDashboardView, SubAdminDashboardView, ExpenseViewSet, ExportReportView, TopProductsView, GSTReportView

urlpatterns = [
    path('revenue/', RevenueReportView.as_view(), name='revenue-report'),
    path('gst/', GSTReportView.as_view(), name='gst-report'),
    path('dashboard/', GlobalDashboardView.as_view(), name='global-dashboard'),
    path('top-products/', TopProductsView.as_view(), name='top-products'),
    path('subadmin-dashboard/', SubAdminDashboardView.as_view(), name='subadmin-dashboard'),
]

from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')

urlpatterns.append(path('export/', ExportReportView.as_view(), name='export-report'))
urlpatterns.extend(router.urls)
