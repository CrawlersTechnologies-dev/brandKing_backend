from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BranchStockViewSet, BarcodeScanView, InventoryInwardView, SerializedItemViewSet

router = DefaultRouter()
router.register(r'stock', BranchStockViewSet, basename='branchstock')
router.register(r'items', SerializedItemViewSet, basename='serializeditem')

urlpatterns = [
    path('', include(router.urls)),
    path('scan/', BarcodeScanView.as_view(), name='barcode-scan'),
    path('inward/', InventoryInwardView.as_view(), name='inventory-inward'),
]
