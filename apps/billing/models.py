import uuid
from django.db import models
from django.conf import settings
from apps.products.models import Product
from apps.branches.models import Branch
from apps.inventory.models import SerializedItem

class Cart(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT)
    counter = models.ForeignKey('branches.Counter', on_delete=models.RESTRICT, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'

class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    serialized_item = models.OneToOneField(SerializedItem, on_delete=models.RESTRICT) # One physical item can only be in one cart item
    price = models.DecimalField(max_digits=10, decimal_places=2) # Current selling price
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cart_items'

class Invoice(models.Model):
    PAYMENT_MODES = (
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('UPI', 'UPI')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT)
    counter = models.ForeignKey('branches.Counter', on_delete=models.RESTRICT, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    
    total_taxable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_igst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoices'

class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    serialized_item = models.ForeignKey(SerializedItem, on_delete=models.RESTRICT)
    
    product_name_snapshot = models.CharField(max_length=255)
    hsn_code_snapshot = models.CharField(max_length=50)
    gst_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    final_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    final_line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'invoice_items'

    def __str__(self):
        return f"{self.product_name_snapshot} - {self.final_line_total}"

class ExchangeRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Stock Updated'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Exchange Completed')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT)
    invoice = models.ForeignKey(Invoice, on_delete=models.RESTRICT, related_name='exchange_requests')
    invoice_item = models.ForeignKey(InvoiceItem, on_delete=models.RESTRICT)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='exchange_requests')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_exchanges')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exchange_requests'
