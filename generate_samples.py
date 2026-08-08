import os
import sys
import django

# Add project to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.products.models import Product, ProductType, HSNCode, GSTRate
from apps.inventory.models import SerializedItem
from apps.branches.models import Branch
from apps.barcodes.services import LabelPrinterService
from apps.billing.services import ReceiptPrinterService
from apps.billing.models import Invoice, InvoiceItem
from apps.accounts.models import User
from django.utils import timezone

# Setup mock data safely
admin, _ = User.objects.get_or_create(email='admin@brandking.com')
branch, _ = Branch.objects.get_or_create(name='Sample Branch', code='SMP')
pt, _ = ProductType.objects.get_or_create(name='Shirt')
now = timezone.now().date()
hsn, _ = HSNCode.objects.get_or_create(code='9999', defaults={'effective_from': now})
gst, _ = GSTRate.objects.get_or_create(name='18%', defaults={'rate_percentage': 18.0, 'effective_from': now})

hsn.default_gst_rate = gst
hsn.save()

product, _ = Product.objects.get_or_create(
    product_code='SMP-01',
    defaults={
        'name': 'Sample Premium Cotton Shirt',
        'product_type': pt,
        'hsn_code': hsn,
        'gst_rate': gst,
        'mrp': 1999.00,
        'selling_price': 1599.00,
        'purchase_price': 800.00,
        'barcode': 'BK000999',
        'created_by': admin
    }
)

item, _ = SerializedItem.objects.get_or_create(
    barcode='BK000999-01',
    defaults={
        'product': product,
        'branch': branch,
        'status': 'IN_STOCK'
    }
)

# 1. Generate Label PDF
pdf_buffer = LabelPrinterService.generate_labels_pdf([item], include_selling_price=True)
with open('C:/Users/admin/.gemini/antigravity/brain/8e2a27c6-f5b4-4fe8-a795-ff3b0b9155f1/scratch/sample_label.pdf', 'wb') as f:
    f.write(pdf_buffer.getvalue())

# 2. Generate Receipt PDF
invoice, _ = Invoice.objects.get_or_create(
    invoice_number='INV-SMP-0001',
    defaults={
        'branch': branch,
        'created_by': admin,
        'subtotal': 1599.00,
        'tax_amount': 287.82,
        'grand_total': 1599.00,
        'payment_mode': 'UPI',
        'customer_phone': '9876543210'
    }
)

InvoiceItem.objects.get_or_create(
    invoice=invoice,
    serialized_item=item,
    defaults={
        'product_name_snapshot': product.name,
        'barcode_snapshot': item.barcode,
        'hsn_code_snapshot': hsn.code,
        'gst_rate_snapshot': 18.0,
        'original_selling_price': 1599.00,
        'discount_amount': 0,
        'final_selling_price': 1599.00,
        'tax_amount': 287.82,
        'final_line_total': 1599.00
    }
)

receipt_buffer = ReceiptPrinterService.generate_receipt_pdf(invoice)
with open('C:/Users/admin/.gemini/antigravity/brain/8e2a27c6-f5b4-4fe8-a795-ff3b0b9155f1/scratch/sample_receipt.pdf', 'wb') as f:
    f.write(receipt_buffer.getvalue())

print('Successfully generated PDFs!')
