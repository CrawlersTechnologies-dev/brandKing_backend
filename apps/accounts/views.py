from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsGlobalAdmin
from common.responses import success_response, error_response
from .models import User, UserDocument
from .serializers import UserSerializer, UserDocumentSerializer, DocumentVerifySerializer
from .permissions import IsDocumentOwnerOrAdminOrSubAdmin
from apps.audit.services import AuditService
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404

def handle_documents(user, request):
    doc_mapping = {
        'profile_photo': 'PROFILE_PHOTO',
        'aadhaar': 'AADHAAR',
        'pan': 'PAN',
        'address_proof': 'ADDRESS_PROOF',
        'other_document': 'OTHER'
    }
    for key, doc_type in doc_mapping.items():
        if key in request.FILES:
            file_obj = request.FILES[key]
            doc, created = UserDocument.objects.update_or_create(
                user=user, 
                document_type=doc_type,
                defaults={'file': file_obj}
            )
            # Log audit
            action = 'CREATED' if created else 'UPDATED'
            AuditService.log(
                user=request.user,
                action=action,
                module='ACCOUNTS',
                object_type='UserDocument',
                object_id=doc.id,
                new_value={'document_type': doc.document_type}
            )

    if 'id_proof' in request.FILES:
        doc_type = request.data.get('id_proof_type', 'OTHER')
        file_obj = request.FILES['id_proof']
        doc, created = UserDocument.objects.update_or_create(
            user=user,
            document_type=doc_type,
            defaults={'file': file_obj}
        )
        action = 'CREATED' if created else 'UPDATED'
        AuditService.log(
            user=request.user,
            action=action,
            module='ACCOUNTS',
            object_type='UserDocument',
            object_id=doc.id,
            new_value={'document_type': doc.document_type}
        )

from common.constants import ROLE_ADMIN, ROLE_SUB_ADMIN, ROLE_CASHIER, ROLE_STORE_STAFF
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.response import Response

class SubAdminViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role=ROLE_SUB_ADMIN).order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsGlobalAdmin]

    def list(self, request, *args, **kwargs):
        branch_id = request.query_params.get('branch_id')
        queryset = self.get_queryset()
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Sub-Admins fetched successfully")

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['role'] = ROLE_SUB_ADMIN
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        AuditService.log(
            user=request.user,
            action='CREATED',
            module='ACCOUNTS',
            object_type='User',
            object_id=serializer.instance.id,
            new_value={'email': serializer.instance.email, 'role': ROLE_SUB_ADMIN}
        )
        
        handle_documents(serializer.instance, request)
        return success_response(data=serializer.data, message="Sub-Admin created successfully", status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_email = instance.email
        response = super().update(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='UPDATED',
            module='ACCOUNTS',
            object_type='User',
            object_id=instance.id,
            old_value={'email': old_email},
            new_value={'email': instance.email}
        )
        
        handle_documents(instance, request)
        # Re-fetch data to include new documents
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data, message="Sub-Admin updated successfully")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = instance.id
        super().destroy(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='DELETED',
            module='ACCOUNTS',
            object_type='User',
            object_id=user_id
        )
        
        return success_response(message="Sub-Admin deleted successfully", status=200)

    @action(detail=True, methods=['post'], url_path='assign-branch')
    def assign_branch(self, request, pk=None):
        instance = self.get_object()
        branch_id = request.data.get('branch')
        
        if not branch_id:
            return error_response(message="branch is required.", status=400)
            
        try:
            from apps.branches.models import Branch
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            return error_response(message="Branch not found.", status=404)
            
        instance.branch = branch
        instance.save()
        
        AuditService.log(
            user=request.user,
            action='BRANCH_ASSIGNED',
            module='ACCOUNTS',
            object_type='User',
            object_id=instance.id,
            new_value={'branch_id': str(branch.id), 'branch_name': branch.name}
        )
        
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data, message="Branch assigned successfully.")

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role__in=[ROLE_CASHIER, ROLE_STORE_STAFF]).order_by('-date_joined')
    serializer_class = UserSerializer
    from common.permissions import IsSubAdmin as SubAdminPermission
    permission_classes = [IsAuthenticated, SubAdminPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == ROLE_SUB_ADMIN:
            qs = qs.filter(branch_id=user.branch_id)
            
        is_approved = self.request.query_params.get('is_approved')
        if is_approved is not None:
            if is_approved.lower() != 'all':
                is_approved_bool = is_approved.lower() in ['true', '1', 't', 'y', 'yes']
                qs = qs.filter(is_approved=is_approved_bool)
        else:
            if getattr(self, 'action', None) == 'list':
                qs = qs.filter(is_approved=True)
            
        return qs

    def list(self, request, *args, **kwargs):
        branch_id = request.query_params.get('branch_id')
        is_approved = request.query_params.get('is_approved')
        
        queryset = self.get_queryset()
        
        if is_approved is not None:
            is_approved_bool = is_approved.lower() in ['true', '1', 't', 'y', 'yes']
            queryset = queryset.filter(is_approved=is_approved_bool)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Employees fetched successfully")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data, message="Employee fetched successfully")

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['role'] = request.data.get('role', ROLE_STORE_STAFF)
        if data['role'] not in [ROLE_CASHIER, ROLE_STORE_STAFF]:
            return error_response(message="Invalid role. Must be CASHIER or STORE_STAFF.")
        
        if request.user.role == ROLE_SUB_ADMIN:
            if not request.user.branch_id:
                raise PermissionDenied("You must be assigned to a branch to create employees.")
            # Force the employee's branch to match the sub-admin's branch
            data['branch'] = str(request.user.branch_id)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        AuditService.log(
            user=request.user,
            action='CREATED',
            module='ACCOUNTS',
            object_type='User',
            object_id=serializer.instance.id,
            new_value={'email': serializer.instance.email, 'role': serializer.instance.role}
        )
        
        # Enforce approval workflow
        if request.user.role == ROLE_SUB_ADMIN:
            serializer.instance.is_approved = False
            serializer.instance.save()
            msg = "Employee created successfully. Pending Global Admin approval."
        else:
            serializer.instance.is_approved = True
            serializer.instance.save()
            msg = "Employee created successfully."

        handle_documents(serializer.instance, request)

        # Re-fetch data to include new documents
        serializer = self.get_serializer(serializer.instance)
        return success_response(data=serializer.data, message=msg, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsGlobalAdmin])
    def approve(self, request, pk=None):
        employee = self.get_object()
        if employee.is_approved:
            return error_response(message="Employee is already approved.", status=400)
        
        employee.is_approved = True
        employee.save()
        
        AuditService.log(request.user, 'APPROVE_USER', 'USER', 'User', employee.id, new_value={'is_approved': True})
        return success_response(message="Employee approved successfully. They can now log in.")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Prevent Sub-Admins from changing branch assignment
        if request.user.role == ROLE_SUB_ADMIN and 'branch' in request.data:
            if request.data['branch'] and str(request.data['branch']) != str(instance.branch_id):
                raise PermissionDenied("Only Global Admins can reassign an employee to a different branch.")

        old_email = instance.email
        response = super().update(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='UPDATED',
            module='ACCOUNTS',
            object_type='User',
            object_id=instance.id,
            old_value={'email': old_email},
            new_value={'email': instance.email}
        )
        
        handle_documents(instance, request)
        # Re-fetch data to include new documents
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data, message="Employee updated successfully")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = instance.id
        super().destroy(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='DELETED',
            module='ACCOUNTS',
            object_type='User',
            object_id=user_id
        )
        
        return success_response(message="Employee deleted successfully", status=200)

    @action(detail=True, methods=['post'], url_path='assign-branch', permission_classes=[IsAuthenticated, IsGlobalAdmin])
    def assign_branch(self, request, pk=None):
        instance = self.get_object()
        branch_id = request.data.get('branch')
        
        if not branch_id:
            return error_response(message="branch is required.", status=400)
            
        try:
            from apps.branches.models import Branch
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            return error_response(message="Branch not found.", status=404)
            
        instance.branch = branch
        instance.save()
        
        AuditService.log(
            user=request.user,
            action='BRANCH_ASSIGNED',
            module='ACCOUNTS',
            object_type='User',
            object_id=instance.id,
            new_value={'branch_id': str(branch.id), 'branch_name': branch.name}
        )
        
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data, message="Branch assigned successfully.")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserSerializer(request.user)
    return success_response(data=serializer.data, message="User profile fetched successfully")

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response(message="Successfully logged out.")
        except Exception as e:
            return error_response(message="Invalid token or token already blacklisted.", status=400)

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = UserDocumentSerializer
    permission_classes = [IsAuthenticated, IsDocumentOwnerOrAdminOrSubAdmin]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        # Check permission to access this user's documents
        self.check_object_permissions(self.request, user)
        return UserDocument.objects.filter(user_id=user_id).order_by('-uploaded_at')

    def create(self, request, *args, **kwargs):
        user_id = self.kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        self.check_object_permissions(self.request, user)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(user=user)
        
        AuditService.log(
            user=request.user,
            action='CREATED',
            module='ACCOUNTS',
            object_type='UserDocument',
            object_id=doc.id,
            new_value={'document_type': doc.document_type}
        )
        return success_response(data=serializer.data, message="Document uploaded successfully", status=201)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = self.kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        self.check_object_permissions(self.request, user)

        # If Global Admin is verifying
        if 'is_verified' in request.data:
            if request.user.role != ROLE_ADMIN:
                raise PermissionDenied("Only Global Admin can verify documents.")
            
            verify_serializer = DocumentVerifySerializer(instance, data=request.data, partial=True)
            verify_serializer.is_valid(raise_exception=True)
            
            old_verified = instance.is_verified
            verify_serializer.save(
                verified_by=request.user,
                verified_at=timezone.now()
            )
            
            AuditService.log(
                user=request.user,
                action='VERIFIED',
                module='ACCOUNTS',
                object_type='UserDocument',
                object_id=instance.id,
                old_value={'is_verified': old_verified},
                new_value={'is_verified': instance.is_verified, 'remarks': instance.remarks}
            )
            return success_response(data=self.get_serializer(instance).data, message="Document verified successfully")

        # Regular update
        old_type = instance.document_type
        response = super().partial_update(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='UPDATED',
            module='ACCOUNTS',
            object_type='UserDocument',
            object_id=instance.id,
            old_value={'document_type': old_type},
            new_value={'document_type': instance.document_type}
        )
        return success_response(data=response.data, message="Document updated successfully")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = self.kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        self.check_object_permissions(self.request, user)
        
        doc_id = instance.id
        doc_type = instance.document_type
        
        super().destroy(request, *args, **kwargs)
        
        AuditService.log(
            user=request.user,
            action='DELETED',
            module='ACCOUNTS',
            object_type='UserDocument',
            object_id=doc_id,
            old_value={'document_type': doc_type}
        )
        return success_response(message="Document deleted successfully", status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDocumentOwnerOrAdminOrSubAdmin])
def serve_document(request, document_id):
    doc = get_object_or_404(UserDocument, id=document_id)
    # Check permissions based on the user the document belongs to
    from rest_framework.permissions import BasePermission
    perm = IsDocumentOwnerOrAdminOrSubAdmin()
    if not perm.has_object_permission(request, None, doc.user):
        raise PermissionDenied("You do not have permission to access this document.")
    
    if not doc.file:
        raise Http404("File not found.")
        
    response = FileResponse(doc.file.open('rb'))
    return response


from django.core.mail import send_mail
from .models import PasswordResetOTP
from .serializers import ForgotPasswordRequestSerializer, ResetPasswordRequestSerializer
from django.conf import settings
import random
from rest_framework.permissions import AllowAny

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        if not user:
            return success_response(message='If the email exists, an OTP has been sent.')
        
        # Hardcoded for testing
        otp = '123456'
        PasswordResetOTP.objects.create(user=user, otp=otp)
        
        send_mail(
            'Password Reset OTP',
            f'Your OTP for password reset is {otp}. It is valid for 10 minutes.',
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@brandking.com'),
            [email],
            fail_silently=False,
        )
        return success_response(message='If the email exists, an OTP has been sent.')

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        user = User.objects.filter(email=email).first()
        if not user:
            return error_response(message='Invalid email or OTP.', status=400)
            
        otp_record = PasswordResetOTP.objects.filter(user=user, otp=otp, is_used=False).order_by('-created_at').first()
        if not otp_record:
            return error_response(message='Invalid email or OTP.', status=400)
            
        from datetime import timedelta
        if timezone.now() > otp_record.created_at + timedelta(minutes=10):
            return error_response(message='OTP has expired.', status=400)
            
        user.set_password(new_password)
        user.save()
        
        otp_record.is_used = True
        otp_record.save()
        
        AuditService.log(
            user=user,
            action='PASSWORD_RESET',
            module='ACCOUNTS',
            object_type='User',
            object_id=user.id
        )
        
        return success_response(message='Password reset successfully.')

from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsGlobalAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        is_approved = self.request.query_params.get('is_approved')
        if is_approved is not None:
            if is_approved.lower() != 'all':
                is_approved_bool = is_approved.lower() in ['true', '1', 't', 'y', 'yes']
                qs = qs.filter(is_approved=is_approved_bool)
        else:
            if getattr(self, 'action', None) == 'list':
                qs = qs.filter(is_approved=True)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        handle_documents(serializer.instance, request)
        
        # Re-fetch data to include new documents
        serializer = self.get_serializer(serializer.instance)
        return success_response(data=serializer.data, message="User created successfully", status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsGlobalAdmin])
    def approve(self, request, pk=None):
        user_obj = self.get_object()
        if user_obj.is_approved:
            return error_response(message="User is already approved.", status=400)

        user_obj.is_approved = True
        user_obj.save()

        AuditService.log(request.user, 'APPROVE_USER', 'USER', 'User', user_obj.id, new_value={'is_approved': True})
        return success_response(message="User approved successfully. They can now log in.")

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        handle_documents(self.get_object(), request)
        
        # Re-fetch data to include new documents
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data, message="User updated successfully")
