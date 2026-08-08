from django.urls import path
from .views import LabelPrintView

urlpatterns = [
    path('print/', LabelPrintView.as_view(), name='label-print'),
]
