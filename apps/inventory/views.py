from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsSubAdmin, IsStoreStaff
from common.responses import success_response, error_response
from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from .models import BranchStock, InventoryLog
from .serializers import BranchStockSerializer, InventoryInwardRequestSerializer
from .services import InventoryService

class BranchStockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BranchStockSerializer
    permission_classes = [IsAuthenticated, IsStoreStaff]

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
    permission_classes = [IsAuthenticated, IsStoreStaff]

    def post(self, request):
        barcode = request.data.get('barcode')
        if not barcode:
            return error_response(message="Barcode is required.")
        
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            return error_response(message="Product not found. Needs creation.", status=404)
            
        serializer = ProductSerializer(product)
        data = serializer.data
        
        # Inject stock quantity for the current branch
        branch = request.user.branch
        if not branch:
            # If Global Admin, try to get branch from payload (id, name, or code)
            branch_val = request.data.get('branch') or request.data.get('branch_id')
            if branch_val:
                from apps.branches.models import Branch
                import uuid
                try:
                    uuid.UUID(str(branch_val))
                    branch = Branch.objects.filter(id=branch_val).first()
                except ValueError:
                    branch = Branch.objects.filter(name__iexact=branch_val).first() or Branch.objects.filter(code__iexact=branch_val).first()

        if branch:
            stock = BranchStock.objects.filter(product=product, branch=branch).first()
            data['stock_quantity'] = stock.quantity if stock else 0
            data['branch_name'] = branch.name
        else:
            # If still no branch (Global Admin didn't specify one), calculate total global stock across all branches
            from django.db.models import Sum
            total_stock = BranchStock.objects.filter(product=product).aggregate(total=Sum('quantity'))['total']
            data['stock_quantity'] = total_stock if total_stock else 0
            data['branch_name'] = "Global (All Branches)"
        
        return success_response(data=data, message="Product found.")

class InventoryInwardView(APIView):
    permission_classes = [IsAuthenticated, IsStoreStaff]

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
