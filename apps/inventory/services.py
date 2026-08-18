from django.db import transaction
from apps.products.models import Product
from apps.inventory.models import BranchStock, InventoryLog
from apps.purchases.models import InventoryInward
from apps.barcodes.services import BarcodeService
from apps.audit.services import AuditService
from apps.billing.services import TaxCalculationService

class InventoryService:
    @staticmethod
    @transaction.atomic
    def process_inward(user, branch, items, reference_number=None, remarks=None):
        """
        Atomically processes an inward transaction.
        items: List of dicts. 
               Each dict should have 'quantity' and either 'barcode' (for existing) 
               or product data (for new product creation).
        """
        inward_record = InventoryInward.objects.create(
            branch=branch,
            reference_number=reference_number,
            remarks=remarks,
            created_by=user,
            total_quantity=sum(item.get('quantity', 0) for item in items)
        )

        for item in items:
            quantity = int(item.get('quantity', 0))
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")

            product_code = item.get('product_code')
            
            # If a name is provided along with product_code, it means we are creating a new product
            if product_code and not item.get('name'):
                # Check if product exists
                product = Product.objects.filter(product_code=product_code).first()
                if not product:
                    raise ValueError(f"Product with SKU {product_code} not found.")
            else:
                # Use ProductSerializer to create the product and handle all mapping/validation
                from apps.products.serializers import ProductSerializer
                product_data = {
                    'name': item.get('name'),
                    'category': item.get('category'),
                    'brand': item.get('brand'),
                    'product_type': item.get('product_type'),
                    'hsn_code': item.get('hsn_code'),
                    'gst_rate': item.get('gst_rate'),
                    'size': item.get('size'),
                    'colour': item.get('colour'),
                    'mrp': item.get('mrp'),
                    'selling_price': item.get('selling_price'),
                    'purchase_price': item.get('purchase_price')
                }
                # Remove None values
                product_data = {k: v for k, v in product_data.items() if v is not None}
                
                serializer = ProductSerializer(data=product_data)
                if not serializer.is_valid():
                    raise ValueError(f"Invalid product data: {serializer.errors}")
                
                product = serializer.save(created_by=user)

                AuditService.log(user, 'CREATE_INWARD', 'PRODUCT', 'Product', product.id, new_value=item)

            # Update Branch Stock
            stock, created = BranchStock.objects.get_or_create(
                branch=branch,
                product=product,
                defaults={'quantity': 0}
            )
            
            stock.quantity += quantity
            stock.save()

            # Auto-generate physical SerializedItem units for barcode scanning
            from apps.inventory.models import SerializedItem
            
            serialized_items_to_create = []
            for i in range(1, quantity + 1):
                # Each physical item gets a completely unique global barcode (e.g. BK000001, BK000002)
                item_barcode = BarcodeService.generate_proprietary_barcode()
                serialized_items_to_create.append(
                    SerializedItem(
                        product=product,
                        branch=branch,
                        barcode=item_barcode,
                        status='IN_STOCK'
                    )
                )
            
            if serialized_items_to_create:
                SerializedItem.objects.bulk_create(serialized_items_to_create)

            # Create Inventory Log
            InventoryLog.objects.create(
                branch=branch,
                product=product,
                change_type='INWARD',
                quantity_change=quantity,
                resulting_quantity=stock.quantity,
                reference_id=str(inward_record.id),
                created_by=user
            )

        return inward_record
