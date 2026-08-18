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
    product_code = serializers.CharField(required=False, allow_blank=True, help_text="SKU/Code of the product to inward")
    quantity = serializers.IntegerField(min_value=1)
    
    # New product fields (Required if product_code/sku is not provided)
    name = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    product_type = serializers.CharField(required=False)
    hsn_code = serializers.CharField(required=False)
    gst_rate = serializers.CharField(required=False, allow_null=True)
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    # Optional fields for new product
    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    brand = serializers.CharField(required=False, allow_null=True)
    size = serializers.CharField(required=False, allow_blank=True)
    colour = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True) # Wait, remarks goes on the InwardRequestSerializer, not Item. But wait, user said "Optional: Remarks". It might be item level or request level. Let's put it on InwardRequestSerializer.

    def validate(self, data):
        if not data.get('product_code') or ('name' in data and 'product_code' in data):
            required_new = ['name', 'category', 'product_type', 'hsn_code', 'mrp', 'selling_price']
            missing = [f for f in required_new if not data.get(f)]
            if missing:
                raise serializers.ValidationError(f"Missing required fields for new product creation: {', '.join(missing)}")
        return data

class InventoryInwardRequestSerializer(serializers.Serializer):
    reference_number = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    branch_id = serializers.UUIDField(required=False, help_text="Required for Global Admins who are not assigned to a specific branch")
    items = InwardItemSerializer(many=True, allow_empty=False)
