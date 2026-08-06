import uuid
from django.db import models
from django.conf import settings
from apps.branches.models import Branch
from apps.products.models import Product

class BranchStock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, related_name='branch_stocks')
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'branch_stocks'
        unique_together = ('branch', 'product')

    def __str__(self):
        return f"{self.product.name} @ {self.branch.name} : {self.quantity}"

class InventoryLog(models.Model):
    CHANGE_TYPES = (
        ('INWARD', 'Inward'),
        ('OUTWARD', 'Outward'),
        ('ADJUSTMENT', 'Adjustment'),
        ('RETURN', 'Return')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT)
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    quantity_change = models.IntegerField()
    resulting_quantity = models.IntegerField()
    reference_id = models.CharField(max_length=100, blank=True, null=True) # e.g. Inward/Invoice ID
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.change_type} {self.quantity_change} of {self.product.name}"

class SerializedItem(models.Model):
    STATUS_CHOICES = (
        ('IN_STOCK', 'In Stock'),
        ('IN_CART', 'In Cart'),
        ('SOLD', 'Sold'),
        ('RETURNED', 'Returned'),
        ('DEFECTIVE', 'Defective')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, related_name='serialized_items')
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT, related_name='serialized_items')
    barcode = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_STOCK')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'serialized_items'

    def __str__(self):
        return f"{self.barcode} - {self.product.name} ({self.status})"
