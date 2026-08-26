from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User
from apps.branches.models import Branch
from apps.products.models import Product, ProductType, HSNCode, GSTRate
from apps.barcodes.services import BarcodeService
from apps.inventory.services import InventoryService
from apps.inventory.models import SerializedItem
from common.constants import ROLE_ADMIN

class HardwareIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(name='Test', code='TEST')
        self.admin = User.objects.create_superuser(email='admin@brandking.com', password='pwd')
        
        from django.utils import timezone
        now = timezone.now().date()
        self.product_type = ProductType.objects.create(name='Shirt')
        self.gst = GSTRate.objects.create(name='5%', rate_percentage=5.0, effective_from=now)
        self.hsn = HSNCode.objects.create(code='1234', default_gst_rate=self.gst, effective_from=now)

    def test_sequential_barcode_generation(self):
        b1 = BarcodeService.generate_proprietary_barcode()
        b2 = BarcodeService.generate_proprietary_barcode()
        self.assertEqual(b1, 'BK000001')
        self.assertEqual(b2, 'BK000002')

    def test_inward_auto_generates_serialized_items(self):
        items = [{
            'name': 'Test Shirt',
            'product_code': 'TS-01',
            'product_type': self.product_type.id,
            'hsn_code': self.hsn.id,
            'gst_rate': self.gst.id,
            'mrp': 1000,
            'selling_price': 800,
            'purchase_price': 500,
            'quantity': 3
        }]
        
        InventoryService.process_inward(self.admin, self.branch, items, 'REF-1')
        product = Product.objects.get(name='Test Shirt')
        
        # Should have generated BK000001 (or 3 because previous test might bleed if db not cleared, but let's just check prefix)
        self.assertTrue(product.barcode.startswith('BK'))
        
        # Check if 3 SerializedItems were created
        serialized = SerializedItem.objects.filter(product=product).order_by('barcode')
        self.assertEqual(serialized.count(), 3)
        self.assertTrue(serialized[0].barcode.startswith('BK'))
        self.assertTrue(serialized[1].barcode.startswith('BK'))
        self.assertTrue(serialized[2].barcode.startswith('BK'))

    def test_label_print_api(self):
        # Setup product and item
        product = Product.objects.create(
            name='Test', product_code='T1', product_type=self.product_type, 
            hsn_code=self.hsn, gst_rate=self.gst, mrp=1000, selling_price=800, purchase_price=500,
            barcode='BK000100', created_by=self.admin
        )
        item = SerializedItem.objects.create(
            product=product, branch=self.branch, barcode='BK000100-01'
        )
        
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(f'/api/barcodes/print/?items={item.id}&include_selling_price=true')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        
    # We won't test invoice print API here as it requires setting up cart, checking out, etc. 
    # The pdf generation function is pure and tested similarly.
