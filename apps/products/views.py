from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from common.permissions import IsSubAdmin, IsBranchStaff
from common.constants import ROLE_STORE_STAFF
from common.responses import success_response, error_response
from apps.audit.services import AuditService
from apps.billing.services import TaxCalculationService

from django.http import HttpResponse
from .models import ProductType, GSTRate, HSNCode, Product, Category, Brand, TemporaryBulkUpload
from .services import BulkImportService
import pandas as pd
import io
from .serializers import (
    ProductTypeSerializer, GSTRateSerializer, 
    HSNCodeSerializer, ProductSerializer,
    CategorySerializer, BrandSerializer
)

class BaseMasterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSubAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(data=serializer.data, message=f"{self.queryset.model.__name__} created successfully", status=201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(data=serializer.data, message=f"{self.queryset.model.__name__} updated successfully")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success_response(message=f"{self.queryset.model.__name__} deleted successfully", status=200)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        AuditService.log(
            self.request.user, 'CREATE', 'MASTER_DATA', 
            instance.__class__.__name__, instance.id, new_value=serializer.data
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_value = self.get_serializer(instance).data
        updated_instance = serializer.save(updated_by=self.request.user)
        AuditService.log(
            self.request.user, 'UPDATE', 'MASTER_DATA', 
            updated_instance.__class__.__name__, updated_instance.id, 
            old_value=old_value, new_value=serializer.data
        )

    def perform_destroy(self, instance):
        if hasattr(instance, 'is_active'):
            instance.is_active = False
            instance.save()
            AuditService.log(
                self.request.user, 'DEACTIVATE', 'MASTER_DATA', 
                instance.__class__.__name__, instance.id
            )
        else:
            super().perform_destroy(instance)


class ProductTypeViewSet(BaseMasterViewSet):
    queryset = ProductType.objects.all().order_by('-created_at')
    serializer_class = ProductTypeSerializer

class CategoryViewSet(BaseMasterViewSet):
    queryset = Category.objects.all().order_by('-created_at')
    serializer_class = CategorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        is_parent = self.request.query_params.get('is_parent')
        if is_parent and is_parent.lower() in ['true', '1', 't', 'y']:
            qs = qs.filter(parent__isnull=True)
            
        parent_name = self.request.query_params.get('parent')
        if parent_name:
            if parent_name.isdigit():
                qs = qs.filter(parent_id=parent_name)
            else:
                qs = qs.filter(parent__name__iexact=parent_name)
                
        return qs

class BrandViewSet(BaseMasterViewSet):
    queryset = Brand.objects.all().order_by('-created_at')
    serializer_class = BrandSerializer

class GSTRateViewSet(BaseMasterViewSet):
    queryset = GSTRate.objects.all().order_by('-created_at')
    serializer_class = GSTRateSerializer


class HSNCodeViewSet(BaseMasterViewSet):
    queryset = HSNCode.objects.all().order_by('-created_at')
    serializer_class = HSNCodeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'description']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsBranchStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'brand', 'product_type', 'hsn_code', 'gst_rate', 'is_active', 'is_locked']
    search_fields = ['name', 'product_code', 'barcode']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(data=serializer.data, message="Product created successfully", status=201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(data=serializer.data, message="Product updated successfully")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success_response(message="Product deleted successfully", status=200)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        AuditService.log(
            self.request.user, 'CREATE', 'PRODUCT', 
            'Product', instance.id, new_value=serializer.data
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_value = self.get_serializer(instance).data
        
        # Locking logic checks
        if instance.is_locked:
            locked_fields = ['name', 'brand', 'category', 'product_type', 'mrp', 'hsn_code', 'gst_rate']
            attempted_changes = [f for f in locked_fields if f in self.request.data and self.request.data[f] != getattr(instance, f)]
            
            if attempted_changes:
                if self.request.user.role == ROLE_STORE_STAFF:
                    raise PermissionDenied("This product is locked and cannot be modified by your role.")
                
                # If SubAdmin/Admin, we allow it but make sure it logs as an override
                AuditService.log(
                    self.request.user, 'OVERRIDE_LOCKED_PRODUCT', 'PRODUCT', 
                    'Product', instance.id, old_value=old_value, new_value=self.request.data
                )

        updated_instance = serializer.save(updated_by=self.request.user)
        
        # Normal update log
        AuditService.log(
            self.request.user, 'UPDATE', 'PRODUCT', 
            'Product', updated_instance.id, old_value=old_value, new_value=serializer.data
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        AuditService.log(
            self.request.user, 'DEACTIVATE', 'PRODUCT', 
            'Product', instance.id
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsSubAdmin])
    def lock(self, request, pk=None):
        product = self.get_object()
        if product.is_locked:
            return success_response(message="Product is already locked.")
            
        product.is_locked = True
        product.save()
        
        AuditService.log(
            request.user, 'LOCK', 'PRODUCT', 'Product', product.id
        )
        return success_response(message="Product locked successfully.")

class BulkProductImportViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsSubAdmin]

    @action(detail=False, methods=['get'])
    def template(self, request):
        df = pd.DataFrame(columns=BulkImportService.EXPECTED_COLUMNS)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        
        response = HttpResponse(
            output.read(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="product_bulk_import_template.xlsx"'
        return response

    @action(detail=False, methods=['post'])
    def validate(self, request):
        if 'file' not in request.FILES:
            return error_response(message="No file provided.", status=400)
            
        file_obj = request.FILES['file']
        if not file_obj.name.endswith(('.csv', '.xlsx')):
            return error_response(message="Invalid file type. Only CSV and XLSX allowed.", status=400)

        temp_upload = TemporaryBulkUpload.objects.create(
            file=file_obj,
            uploaded_by=request.user
        )
        
        try:
            with temp_upload.file.open('rb') as f:
                validation_result = BulkImportService.validate_file(f)
            validation_result['file_id'] = str(temp_upload.id)
            return success_response(data=validation_result, message="File validated successfully.")
        except Exception as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        file_id = request.data.get('file_id')
        import_only_valid = request.data.get('import_only_valid', False)
        
        if not file_id:
            return error_response(message="file_id is required.", status=400)
            
        try:
            temp_upload = TemporaryBulkUpload.objects.get(id=file_id, uploaded_by=request.user)
        except TemporaryBulkUpload.DoesNotExist:
            return error_response(message="Invalid or expired file_id.", status=404)
            
        try:
            with temp_upload.file.open('rb') as f:
                success_count, invalid_count = BulkImportService.confirm_import(f, request.user, import_only_valid)
            
            temp_upload.delete()
            return success_response(message=f"Successfully imported {success_count} products.")
        except Exception as e:
            return error_response(message=str(e), status=400)

    @action(detail=True, methods=['get'])
    def errors(self, request, pk=None):
        try:
            temp_upload = TemporaryBulkUpload.objects.get(id=pk, uploaded_by=request.user)
        except TemporaryBulkUpload.DoesNotExist:
            return error_response(message="Invalid or expired file_id.", status=404)
            
        try:
            with temp_upload.file.open('rb') as f:
                df = BulkImportService._parse_file(f)
                
            with temp_upload.file.open('rb') as f:
                validation = BulkImportService.validate_file(f)
                
            if not validation['errors']:
                return error_response(message="No errors found.", status=400)
                
            error_map = {}
            for err in validation['errors']:
                row_idx = err['row'] - 2
                if row_idx not in error_map:
                    error_map[row_idx] = []
                error_map[row_idx].append(f"{err['field']}: {err['error']}")
                
            error_rows = []
            for row_idx in error_map.keys():
                row_data = df.iloc[row_idx].copy()
                row_data['Error_Reason'] = " | ".join(error_map[row_idx])
                error_rows.append(row_data)
                
            error_df = pd.DataFrame(error_rows)
            
            output = io.BytesIO()
            error_df.to_csv(output, index=False)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="import_errors_{pk}.csv"'
            return response
            
        except Exception as e:
            return error_response(message=str(e), status=400)
