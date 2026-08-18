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
    product_code = serializers.CharField(required=False, allow_blank=True)
    sku = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'is_locked']

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else data
        
        def resolve_fk(field, model_class, lookup_fields):
            val = mutable_data.get(field)
            if val:
                from django.db.models import Q
                
                # Try primary key first
                if str(val).isdigit() and model_class.objects.filter(id=val).exists():
                    mutable_data[field] = int(val)
                    return
                        
                # Look up by name/code
                q_objects = Q()
                for lf in lookup_fields:
                    q_objects |= Q(**{f"{lf}__iexact": str(val)})
                
                if model_class == GSTRate and str(val).replace('.','',1).isdigit():
                    q_objects |= Q(rate_percentage=val)
                
                obj = model_class.objects.filter(q_objects).first()
                if obj:
                    mutable_data[field] = obj.id
                else:
                    raise serializers.ValidationError({field: f"No matching {model_class.__name__} found for '{val}'"})

        resolve_fk('category', Category, ['name', 'code'])
        resolve_fk('brand', Brand, ['name', 'code'])
        resolve_fk('product_type', ProductType, ['name', 'code'])
        resolve_fk('hsn_code', HSNCode, ['code'])
        resolve_fk('gst_rate', GSTRate, ['name'])
        
        for bool_field in ['is_active', 'is_locked']:
            if bool_field in mutable_data:
                val = str(mutable_data[bool_field]).lower()
                mutable_data[bool_field] = val in ('true', '1', 't', 'y', 'yes')

        return super().to_internal_value(mutable_data)

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
            
        # Synchronize SKU and Product Code
        if not validated_data.get('sku') and not validated_data.get('product_code'):
            import uuid
            generated_sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
            validated_data['product_code'] = generated_sku
            validated_data['sku'] = generated_sku
        elif validated_data.get('sku') and not validated_data.get('product_code'):
            validated_data['product_code'] = validated_data['sku']
        elif validated_data.get('product_code') and not validated_data.get('sku'):
            validated_data['sku'] = validated_data['product_code']

        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Override the default ID numbers with the actual string names
        representation['category'] = instance.category.name if instance.category else None
        representation['brand'] = instance.brand.name if instance.brand else None
        representation['product_type'] = instance.product_type.name if instance.product_type else None
        representation['hsn_code'] = instance.hsn_code.code if instance.hsn_code else None
        representation['gst_rate'] = instance.gst_rate.name if instance.gst_rate else None
        
        return representation
