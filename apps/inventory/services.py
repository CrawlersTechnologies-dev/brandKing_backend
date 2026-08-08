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
                # Need to create new product
                # Ensure GST calculation works before saving
                mrp = item.get('mrp')
                selling_price = item.get('selling_price')
                purchase_price = item.get('purchase_price') or 0.00
                category_id = item.get('category_id')
                brand_id = item.get('brand_id')
                size = item.get('size')
                colour = item.get('colour')
                
                # Auto generate SKU
                import uuid
                generated_sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
                
                product = Product(
                    name=item.get('name'),
                    product_code=generated_sku, # product_code is SKU now
                    sku=generated_sku,
                    product_type_id=item.get('product_type_id'),
                    category_id=category_id,
                    brand_id=brand_id,
                    size=size,
                    colour=colour,
                    hsn_code_id=item.get('hsn_code_id'),
                    mrp=mrp,
                    selling_price=selling_price,
                    purchase_price=purchase_price,
                    barcode=BarcodeService.generate_proprietary_barcode(branch.code),
                    created_by=user
                )
                # Tax check will raise ValueError if invalid
                TaxCalculationService.get_applicable_gst_rate(product)
                product.save()

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
