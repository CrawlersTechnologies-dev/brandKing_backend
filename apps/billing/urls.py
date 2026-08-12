from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, InvoiceViewSet, ExchangeViewSet, OfferViewSet

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'exchanges', ExchangeViewSet, basename='exchange')
router.register(r'offers', OfferViewSet, basename='offer')

urlpatterns = [
    path('', include(router.urls)),
]
