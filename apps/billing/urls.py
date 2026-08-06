from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, InvoiceViewSet

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [
    path('', include(router.urls)),
]
