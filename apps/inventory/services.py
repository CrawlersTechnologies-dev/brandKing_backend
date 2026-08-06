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
    def process_inward(user, branch, reference_number=None, items=[]):
        """
        Atomically processes an inward transaction.
        items: List of dicts. 
               Each dict should have 'quantity' and either 'barcode' (for existing) 
               or product data (for new product creation).
        """
        inward_record = InventoryInward.objects.create(
            branch=branch,
            reference_number=reference_number,
            created_by=user,
            total_quantity=sum(item.get('quantity', 0) for item in items)
        )

        for item in items:
            quantity = int(item.get('quantity', 0))
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")

            barcode = item.get('barcode')
            
            if barcode:
                # Check if product exists
                product = Product.objects.filter(barcode=barcode).first()
                if not product:
                    raise ValueError(f"Product with barcode {barcode} not found.")
            else:
                # Need to create new product
                # Ensure GST calculation works before saving
                product = Product(
                    name=item.get('name'),
                    product_code=item.get('product_code'),
                    product_type_id=item.get('product_type_id'),
                    hsn_code_id=item.get('hsn_code_id'),
                    gst_rate_id=item.get('gst_rate_id'),
                    mrp=item.get('mrp'),
                    selling_price=item.get('selling_price'),
                    purchase_price=item.get('purchase_price'),
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
