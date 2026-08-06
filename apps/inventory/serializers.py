from rest_framework import serializers
from .models import BranchStock, InventoryLog
from apps.products.serializers import ProductSerializer

class BranchStockSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = BranchStock
        fields = ['id', 'branch', 'product', 'quantity', 'last_updated', 'product_details']

class InventoryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLog
        fields = '__all__'

class InwardItemSerializer(serializers.Serializer):
    barcode = serializers.CharField(required=False, allow_blank=True, help_text="Barcode of existing product")
    quantity = serializers.IntegerField(min_value=1)
    
    # New product fields (Required if barcode is not provided)
    name = serializers.CharField(required=False)
    product_code = serializers.CharField(required=False)
    product_type_id = serializers.IntegerField(required=False)
    hsn_code_id = serializers.IntegerField(required=False)
    gst_rate_id = serializers.IntegerField(required=False, allow_null=True)
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate(self, data):
        if not data.get('barcode'):
            required_new = ['name', 'product_code', 'product_type_id', 'hsn_code_id', 'mrp', 'selling_price', 'purchase_price']
            missing = [f for f in required_new if not data.get(f)]
            if missing:
                raise serializers.ValidationError(f"Missing required fields for new product creation: {', '.join(missing)}")
        return data

class InventoryInwardRequestSerializer(serializers.Serializer):
    reference_number = serializers.CharField(required=False, allow_blank=True)
    items = InwardItemSerializer(many=True, allow_empty=False)
