with open('apps/billing/views.py', 'a') as f:
    f.write('''
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from apps.customers.models import Customer
from apps.inventory.models import InventoryLog, BranchStock
from common.permissions import IsGlobalAdmin
from .models import ExchangeRequest, InvoiceItem
from .serializers import ExchangeRequestSerializer

class ExchangeViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ExchangeRequest.objects.filter(branch=user.branch).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        invoice_item_id = request.data.get('invoice_item')
        reason = request.data.get('reason')

        if not invoice_item_id or not reason:
            return error_response(message="invoice_item and reason are required.", status=400)

        try:
            invoice_item = InvoiceItem.objects.get(id=invoice_item_id, invoice__branch=request.user.branch)
        except InvoiceItem.DoesNotExist:
            return error_response(message="Invoice Item not found.", status=404)

        invoice = invoice_item.invoice

        # Check 72 hours eligibility
        time_since_creation = timezone.now() - invoice.created_at
        if time_since_creation > timedelta(hours=72):
            return error_response(message="Return eligibility expired (72 hours passed).", status=400)

        # Check if already exchanged or pending
        if ExchangeRequest.objects.filter(invoice_item=invoice_item, status__in=['PENDING', 'APPROVED']).exists():
            return error_response(message="Item already has an active exchange request.", status=400)

        exchange = ExchangeRequest.objects.create(
            branch=request.user.branch,
            invoice=invoice,
            invoice_item=invoice_item,
            reason=reason,
            requested_by=request.user,
            status='PENDING'
        )
        serializer = self.get_serializer(exchange)
        return success_response(data=serializer.data, message="Exchange request submitted successfully.", status=201)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsGlobalAdmin])
    def approve(self, request, pk=None):
        exchange = self.get_object()
        if exchange.status != 'PENDING':
            return error_response(message="Only PENDING requests can be approved.", status=400)

        with transaction.atomic():
            exchange.status = 'APPROVED'
            exchange.approved_by = request.user
            exchange.save()

            # Update Stock
            serialized_item = exchange.invoice_item.serialized_item
            serialized_item.status = 'RETURNED'
            serialized_item.save()

            branch_stock, _ = BranchStock.objects.get_or_create(
                branch=exchange.branch,
                product=exchange.invoice_item.product
            )
            branch_stock.quantity += 1
            branch_stock.save()

            InventoryLog.objects.create(
                branch=exchange.branch,
                product=exchange.invoice_item.product,
                change_type='RETURN',
                quantity_change=1,
                resulting_quantity=branch_stock.quantity,
                reference_id=str(exchange.id),
                created_by=request.user
            )

            # Issue Store Credit
            customer_phone = exchange.invoice.customer_phone
            if customer_phone:
                customer, _ = Customer.objects.get_or_create(phone_number=customer_phone)
                customer.store_credit += exchange.invoice_item.final_selling_price
                customer.save()

        return success_response(message="Exchange approved, stock updated, and store credit issued.")
''')
