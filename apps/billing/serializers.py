from rest_framework import serializers
from .models import Cart, CartItem, Invoice, InvoiceItem

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    barcode = serializers.CharField(source='serialized_item.barcode', read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product_name', 'barcode', 'price']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'customer_phone', 'customer_name', 'status', 'created_at', 'items', 'total_amount']

    def get_total_amount(self, obj):
        return sum(item.price for item in obj.items.all())

class InvoiceItemSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='serialized_item.barcode', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'product_name_snapshot', 'barcode', 'hsn_code_snapshot', 'gst_rate_snapshot',
            'original_unit_price', 'discount_amount', 'final_selling_price',
            'taxable_amount', 'cgst_amount', 'sgst_amount', 'igst_amount', 'final_line_total'
        ]

class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer_phone', 'customer_name', 'created_by_name',
            'total_taxable_amount', 'total_cgst', 'total_sgst', 'total_igst', 'grand_total',
            'payment_mode', 'created_at', 'items'
        ]
