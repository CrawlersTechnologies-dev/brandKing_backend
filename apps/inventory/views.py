from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsBranchEmployee
from common.responses import success_response, error_response
from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from .models import BranchStock, InventoryLog
from .serializers import BranchStockSerializer, InventoryInwardRequestSerializer
from .services import InventoryService

class BranchStockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BranchStockSerializer
    permission_classes = [IsAuthenticated, IsBranchEmployee]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            # Admin can see all stocks or filter by branch_id
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                return BranchStock.objects.filter(branch_id=branch_id).select_related('product')
            return BranchStock.objects.all().select_related('product')
        
        # Employees and SubAdmins only see their own branch's stock
        return BranchStock.objects.filter(branch_id=user.branch_id).select_related('product')

class BarcodeScanView(APIView):
    permission_classes = [IsAuthenticated, IsBranchEmployee]

    def post(self, request):
        barcode = request.data.get('barcode')
        if not barcode:
            return error_response(message="Barcode is required.")
        
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            return error_response(message="Product not found. Needs creation.", status=404)
            
        serializer = ProductSerializer(product)
        return success_response(data=serializer.data, message="Product found.")

class InventoryInwardView(APIView):
    permission_classes = [IsAuthenticated, IsBranchEmployee]

    def post(self, request):
        serializer = InventoryInwardRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reference_number = serializer.validated_data.get('reference_number')
        items = serializer.validated_data.get('items')

        # Ensure user belongs to a branch or specifies one
        branch = request.user.branch
        if not branch:
            branch_id = serializer.validated_data.get('branch_id')
            if not branch_id:
                return error_response(message="Since you are a Global Admin (no default branch), you must specify a 'branch_id' in the payload to receive stock.")
            from apps.branches.models import Branch
            branch = Branch.objects.filter(id=branch_id).first()
            if not branch:
                return error_response(message="Invalid branch_id provided.")
        
        try:
            inward_record = InventoryService.process_inward(
                user=request.user,
                branch=branch,
                items=items,
                reference_number=reference_number,
                remarks=serializer.validated_data.get('remarks')
            )
            return success_response(data={'inward_id': str(inward_record.id)}, message="Inventory inward processed successfully.", status=201)
        except ValueError as e:
            return error_response(message=str(e))
        except Exception as e:
            return error_response(message="An unexpected error occurred during inward processing.", errors=str(e), status=500)
