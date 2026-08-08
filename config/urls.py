from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "healthy", "message": "Brand King POS API is running"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    
    # App URLs
    path('api/', include('apps.accounts.urls')),
    path('api/branches/', include('apps.branches.urls')),
    path('api/', include('apps.products.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/barcodes/', include('apps.barcodes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
