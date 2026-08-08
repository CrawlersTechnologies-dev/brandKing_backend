from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Cart, Invoice
from .serializers import CartSerializer, InvoiceSerializer
from .services import CartService, CheckoutService
from common.responses import success_response, error_response
from common.permissions import IsBranchEmployee

class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsBranchEmployee]
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
        if not barcode:
            return error_response(message="Barcode is required.", status=400)
            
        branch = request.user.branch
        try:
            cart = CartService.scan_barcode(request.user, branch, barcode)
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
        
        if not cart_id or not payment_mode:
            return error_response(message="cart_id and payment_mode are required.", status=400)
            
        if payment_mode not in dict(Invoice.PAYMENT_MODES).keys():
            return error_response(message="Invalid payment_mode.", status=400)
            
        try:
            invoice = CheckoutService.process_checkout(
                user=request.user,
                cart_id=cart_id,
                payment_mode=payment_mode,
                customer_phone=customer_phone,
                customer_name=customer_name
            )
            return success_response(data={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number}, message="Checkout successful!")
        except ValueError as e:
            return error_response(message=str(e), status=400)

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsBranchEmployee]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        branch = self.request.user.branch
        return Invoice.objects.filter(branch=branch).order_by('-created_at')

    @action(detail=True, methods=['get'])
    def print(self, request, pk=None):
        from .services import ReceiptPrinterService
        from django.http import HttpResponse
        
        invoice = self.get_object()
        pdf_buffer = ReceiptPrinterService.generate_receipt_pdf(invoice)
        
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{invoice.invoice_number}.pdf"'
        return response
