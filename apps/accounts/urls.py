from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import EmployeeViewSet, SubAdminViewSet, me, LogoutView, DocumentViewSet, serve_document, ForgotPasswordView, ResetPasswordView, CustomTokenObtainPairView

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'sub-admins', SubAdminViewSet, basename='subadmin')

urlpatterns = [
    path('', include(router.urls)),
    
    # Document APIs
    path('employees/<uuid:user_id>/documents/', DocumentViewSet.as_view({'get': 'list', 'post': 'create'}), name='document-list'),
    path('employees/<uuid:user_id>/documents/<uuid:pk>/', DocumentViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='document-detail'),
    path('documents/<uuid:document_id>/serve/', serve_document, name='serve-document'),

    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/me/', me, name='auth_me'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset_password'),
]
