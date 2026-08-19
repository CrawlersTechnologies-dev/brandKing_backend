from django.urls import path
from .views import RevenueReportView, GlobalDashboardView

urlpatterns = [
    path('revenue/', RevenueReportView.as_view(), name='revenue-report'),
    path('dashboard/', GlobalDashboardView.as_view(), name='global-dashboard'),
]
