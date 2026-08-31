from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Cart, Invoice, Shift, ExchangeRequest, Offer
from .serializers import CartSerializer, InvoiceSerializer, ShiftSerializer, ExchangeRequestSerializer, OfferSerializer
from .services import CartService, CheckoutService
from apps.branches.models import Counter
from common.responses import success_response, error_response
from common.permissions import IsCashier

class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCashier]
    serializer_class = CartSerializer

    def get_queryset(self):
        return Cart.objects.filter(created_by=self.request.user)

    def list(self, request):
        branch = request.user.branch
        cart = CartService.get_or_create_active_cart(request.user, branch)
        serializer = self.get_serializer(cart)
        return success_response(data=serializer.data)

    @action(detail=False, methods=['post'])
    def scan(self, request):
        barcode = request.data.get('barcode')
        counter_id = request.data.get('counter_id')
        if not barcode:
            return error_response(message="Barcode is required.", status=400)
        if not counter_id:
            return error_response(message="counter_id is required.", status=400)

        branch = request.user.branch
        try:
            from apps.branches.models import Counter
            counter = Counter.objects.get(id=counter_id, branch=branch)
            cart = CartService.scan_barcode(request.user, branch, barcode, counter=counter)
            serializer = self.get_serializer(cart)
            return success_response(data=serializer.data, message="Item added to cart.")
        except ValueError as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        item_id = request.data.get('item_id')
        if not item_id:
            return error_response(message="item_id is required.", status=400)
            
        try:
            CartService.remove_item(request.user, item_id)
            branch = request.user.branch
            cart = CartService.get_or_create_active_cart(request.user, branch)
            serializer = self.get_serializer(cart)
            return success_response(data=serializer.data, message="Item removed.")
        except ValueError as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['post'])
    def apply_promo(self, request):
        promo_code = request.data.get('promo_code')
        if not promo_code:
            return error_response(message="promo_code is required.", status=400)
            
        branch = request.user.branch
        cart = CartService.get_or_create_active_cart(request.user, branch)
        
        try:
            CartService.apply_promo_code(cart, promo_code)
            serializer = self.get_serializer(cart)
            return success_response(data=serializer.data, message="Promo code applied.")
        except ValueError as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['post'])
    def hold(self, request):
        cart_id = request.data.get('cart_id')
        try:
            CartService.hold_cart(request.user, cart_id)
            return success_response(message="Bill placed on hold.")
        except ValueError as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['get'])
    def held_bills(self, request):
        branch = request.user.branch
        held_carts = Cart.objects.filter(created_by=request.user, branch=branch, status='ON_HOLD').order_by('-updated_at')
        serializer = self.get_serializer(held_carts, many=True)
        return success_response(data=serializer.data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        try:
            cart = CartService.resume_cart(request.user, pk)
            serializer = self.get_serializer(cart)
            return success_response(data=serializer.data, message="Bill resumed.")
        except ValueError as e:
            return error_response(message=str(e), status=400)

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        cart_id = request.data.get('cart_id')
        payment_mode = request.data.get('payment_mode')
        customer_phone = request.data.get('customer_phone')
        customer_name = request.data.get('customer_name')
        counter_id = request.data.get('counter_id')
        apply_credit = request.data.get('apply_credit', False)
        
        if not cart_id or not payment_mode or not counter_id:
            return error_response(message="cart_id, payment_mode, and counter_id are required.", status=400)
            
        if payment_mode not in dict(Invoice.PAYMENT_MODES).keys():
            return error_response(message="Invalid payment mode.", status=400)
            
        try:
            from apps.branches.models import Counter
            from apps.billing.models import Shift
            try:
                counter = Counter.objects.get(id=counter_id, branch=request.user.branch)
            except Counter.DoesNotExist:
                return error_response(message="Counter not found or does not belong to your branch.", status=404)
            
            # Anti-Fraud: Enforce Shift Management
            active_shift = Shift.objects.filter(cashier=request.user, status='OPEN').first()
            if not active_shift:
                return error_response(message="You must open your cash register (start a shift) before processing sales.", status=403)
                
            invoice = CheckoutService.process_checkout(
                user=request.user,
                cart_id=cart_id,
                payment_mode=payment_mode,
                customer_phone=customer_phone,
                customer_name=customer_name,
                counter=counter,
                apply_credit=apply_credit,
                shift=active_shift
            )
            return success_response(data={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number}, message="Checkout successful!")
        except ValueError as e:
            return error_response(message=str(e), status=400)

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCashier]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'ADMIN':
            qs = Invoice.objects.all().order_by('-created_at')
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                qs = qs.filter(branch_id=branch_id)
        else:
            qs = Invoice.objects.filter(branch=user.branch).order_by('-created_at')
        
        invoice_number = self.request.query_params.get('invoice_number')
        if invoice_number:
            qs = qs.filter(invoice_number__icontains=invoice_number)
            
        customer_phone = self.request.query_params.get('customer_phone')
        if customer_phone:
            qs = qs.filter(customer_phone__icontains=customer_phone)
            
        return qs

    @action(detail=True, methods=['get'])
    def print(self, request, pk=None):
        from .services import ReceiptPrinterService
        from django.http import HttpResponse
        
        invoice = self.get_object()
        pdf_buffer = ReceiptPrinterService.generate_receipt_pdf(invoice)
        
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{invoice.invoice_number}.pdf"'
        return response

from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from apps.customers.models import Customer
from apps.inventory.models import InventoryLog, BranchStock
from common.permissions import IsSubAdmin
from .models import ExchangeRequest, InvoiceItem
from .serializers import ExchangeRequestSerializer

class ExchangeViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            qs = ExchangeRequest.objects.all().order_by('-created_at')
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                qs = qs.filter(branch_id=branch_id)
        else:
            qs = ExchangeRequest.objects.filter(branch=user.branch).order_by('-created_at')
            
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status.upper())
            
        return qs

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

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsSubAdmin])
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

from .models import Offer
from .serializers import OfferSerializer
from common.permissions import IsSubAdmin
from common.constants import ROLE_ADMIN
from apps.audit.services import AuditService

class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.all().order_by('-created_at')
    serializer_class = OfferSerializer
    permission_classes = [permissions.IsAuthenticated, IsSubAdmin]
    
    def perform_create(self, serializer):
        user = self.request.user
        status = 'ACTIVE' if user.role == ROLE_ADMIN else 'DRAFT'
        offer = serializer.save(created_by=user, status=status)
        
        AuditService.log(
            user=user,
            action='CREATED_OFFER',
            module='BILLING',
            object_type='Offer',
            object_id=str(offer.id),
            new_value={'name': offer.name, 'status': status}
        )

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def approve(self, request, pk=None):
        offer = self.get_object()
        user = request.user
        
        if user.role != ROLE_ADMIN:
            return error_response(message='Only Global Admins can approve offers.', status=403)
            
        if offer.status != 'DRAFT':
            return error_response(message='Only draft offers can be approved.', status=400)
            
        offer.status = 'ACTIVE'
        offer.approved_by = user
        offer.save()
        
        AuditService.log(
            user=user,
            action='APPROVED_OFFER',
            module='BILLING',
            object_type='Offer',
            object_id=str(offer.id)
        )
        return success_response(message='Offer approved successfully.')

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_status(self, request, pk=None):
        offer = self.get_object()
        user = request.user

        if user.role != ROLE_ADMIN:
            return error_response(message='Only Global Admins can toggle offer status.', status=403)

        if offer.status == 'ACTIVE':
            offer.status = 'EXPIRED'
        elif offer.status == 'EXPIRED':
            offer.status = 'ACTIVE'
        else:
            return error_response(message='Can only toggle status between ACTIVE and EXPIRED.', status=400)

        offer.save()

        AuditService.log(
            user=user,
            action=f'CHANGED_OFFER_STATUS_TO_{offer.status}',
            module='BILLING',
            object_type='Offer',
            object_id=str(offer.id)
        )
        return success_response(message=f'Offer status changed to {offer.status}.')

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_status(self, request, pk=None):
        offer = self.get_object()
        user = request.user

        if user.role != ROLE_ADMIN:
            return error_response(message='Only Global Admins can toggle offer status.', status=403)

        if offer.status == 'ACTIVE':
            offer.status = 'EXPIRED'
        elif offer.status == 'EXPIRED':
            offer.status = 'ACTIVE'
        else:
            return error_response(message='Can only toggle status between ACTIVE and EXPIRED.', status=400)

        offer.save()

        AuditService.log(
            user=user,
            action=f'CHANGED_OFFER_STATUS_TO_{offer.status}',
            module='BILLING',
            object_type='Offer',
            object_id=str(offer.id)
        )
        return success_response(message=f'Offer status changed to {offer.status}.')

from .models import Shift
from .serializers import ShiftSerializer
class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all().order_by('-opened_at')
    serializer_class = ShiftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'SUB_ADMIN':
            qs = qs.filter(branch_id=self.request.user.branch_id)
        elif self.request.user.role in ['CASHIER', 'STORE_STAFF']:
            qs = qs.filter(cashier=self.request.user)
        return qs

    @action(detail=False, methods=['post'])
    def open(self, request):
        counter_name = request.data.get('counter_name')
        opening_balance = request.data.get('opening_balance', 0)

        if not counter_name:
            return error_response(message="counter_name is required", status=400)

        branch = request.user.branch
        if not branch:
            return error_response(message="You are not assigned to any branch.", status=400)

        try:
            counter = Counter.objects.get(name__iexact=counter_name, branch=branch)
        except Counter.DoesNotExist:
            return error_response(message="Counter not found in your branch.", status=404)

        # Check if user already has an open shift
        existing_shift = Shift.objects.filter(cashier=request.user, status='OPEN').first()
        if existing_shift:
            return error_response(message="You already have an open shift.", status=400)

        shift = Shift.objects.create(
            branch=branch,
            counter=counter,
            cashier=request.user,
            opening_balance=opening_balance,
            status='OPEN'
        )

        return success_response(data=ShiftSerializer(shift).data, message="Shift opened successfully")

    @action(detail=False, methods=['post'])
    def close(self, request):
        actual_balance = request.data.get('actual_balance')
        notes = request.data.get('notes', '')

        if actual_balance is None:
            return error_response(message="actual_balance is required", status=400)

        shift = Shift.objects.filter(cashier=request.user, status='OPEN').first()
        if not shift:
            return error_response(message="You do not have an open shift.", status=400)

        # Calculate expected balance
        invoices = Invoice.objects.filter(
            shift=shift,
            payment_method='CASH'
        )
        
        cash_sales = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        expected_balance = shift.opening_balance + cash_sales
        actual_balance = Decimal(str(actual_balance))

        shift.expected_balance = expected_balance
        shift.actual_balance = actual_balance
        shift.closed_at = timezone.now()
        shift.notes = notes

        if expected_balance != actual_balance:
            shift.status = 'DISCREPANCY'
        else:
            shift.status = 'CLOSED'

        shift.save()

        return success_response(data=ShiftSerializer(shift).data, message=f"Shift closed with status: {shift.status}")
