from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductTypeViewSet, GSTRateViewSet, HSNCodeViewSet, ProductViewSet, CategoryViewSet, BrandViewSet, BulkProductImportViewSet

router = DefaultRouter()
router.register(r'product-types', ProductTypeViewSet, basename='producttype')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'gst-rates', GSTRateViewSet, basename='gstrate')
router.register(r'hsn-codes', HSNCodeViewSet, basename='hsncode')
router.register(r'products/bulk-upload', BulkProductImportViewSet, basename='bulk-import')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
]
