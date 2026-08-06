from rest_framework import serializers
from .models import ProductType, GSTRate, HSNCode, Product, Category, Brand
from apps.billing.services import TaxCalculationService

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = '__all__'

class GSTRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTRate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

class HSNCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HSNCode
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

class ProductSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'is_locked']

    def validate(self, data):
        # 1. Price non-negative validations
        if 'mrp' in data and data['mrp'] < 0:
            raise serializers.ValidationError({"mrp": "MRP must not be negative."})
        if 'selling_price' in data and data['selling_price'] < 0:
            raise serializers.ValidationError({"selling_price": "Selling price must not be negative."})
        if 'purchase_price' in data and data['purchase_price'] < 0:
            raise serializers.ValidationError({"purchase_price": "Purchase price must not be negative."})

        # 2. HSN & Product Type Active validations
        if 'hsn_code' in data and not data['hsn_code'].is_active:
            raise serializers.ValidationError({"hsn_code": "Selected HSN code is inactive."})
        if 'product_type' in data and not data['product_type'].is_active:
            raise serializers.ValidationError({"product_type": "Selected Product Type is inactive."})

        return data

    def create(self, validated_data):
        # We need to simulate the product to check GST validation before creation
        mock_product = Product(**validated_data)
        try:
            TaxCalculationService.get_applicable_gst_rate(mock_product)
        except ValueError as e:
            raise serializers.ValidationError({"gst_configuration": str(e)})

        # Automatically generate barcode if not provided
        if not validated_data.get('barcode'):
            from apps.barcodes.services import BarcodeService
            validated_data['barcode'] = BarcodeService.generate_proprietary_barcode(None)

        return super().create(validated_data)
