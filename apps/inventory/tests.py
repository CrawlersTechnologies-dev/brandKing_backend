from django.test import TestCase
from decimal import Decimal
from apps.accounts.models import User
from apps.branches.models import Branch
from apps.products.models import Product, ProductType, GSTRate, HSNCode
from apps.inventory.models import BranchStock, InventoryLog
from apps.inventory.services import InventoryService

class InventoryServiceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test Branch', code='TST')
        self.user = User.objects.create_user(email='test@example.com', branch=self.branch, role='EMPLOYEE')
        
        self.product_type = ProductType.objects.create(name='Regular', code='REG')
        self.gst_rate = GSTRate.objects.create(name='18%', rate_percentage=Decimal('18'), effective_from='2026-01-01')
        self.hsn_code = HSNCode.objects.create(code='1234', default_gst_rate=self.gst_rate, effective_from='2026-01-01')
        
        self.existing_product = Product.objects.create(
            name='Existing Shirt',
            product_code='EX-01',
            barcode='BK-TST-EX1',
            product_type=self.product_type,
            hsn_code=self.hsn_code,
            gst_rate=self.gst_rate,
            mrp=1000, selling_price=1000, purchase_price=500
        )
        
        BranchStock.objects.create(branch=self.branch, product=self.existing_product, quantity=5)

    def test_inward_existing_product(self):
        items = [{'barcode': 'BK-TST-EX1', 'quantity': 10}]
        InventoryService.process_inward(self.user, self.branch, items=items)
        
        stock = BranchStock.objects.get(branch=self.branch, product=self.existing_product)
        self.assertEqual(stock.quantity, 15)
        
        logs = InventoryLog.objects.filter(product=self.existing_product)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().quantity_change, 10)

    def test_inward_new_product(self):
        items = [{
            'quantity': 20,
            'name': 'New Shoes',
            'product_code': 'NS-01',
            'product_type_id': self.product_type.id,
            'hsn_code_id': self.hsn_code.id,
            'mrp': 2000,
            'selling_price': 1800,
            'purchase_price': 1000
        }]
        InventoryService.process_inward(self.user, self.branch, items=items)
        
        # New product should have been created
        new_product = Product.objects.get(product_code='NS-01')
        self.assertTrue(new_product.barcode.startswith('BK-TST-'))
        
        stock = BranchStock.objects.get(branch=self.branch, product=new_product)
        self.assertEqual(stock.quantity, 20)
        
        logs = InventoryLog.objects.filter(product=new_product)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().quantity_change, 20)

    def test_inward_mixed_payload(self):
        items = [
            {'barcode': 'BK-TST-EX1', 'quantity': 2}, # existing
            {
                'quantity': 5,
                'name': 'New Hat',
                'product_code': 'NH-01',
                'product_type_id': self.product_type.id,
                'hsn_code_id': self.hsn_code.id,
                'mrp': 500, 'selling_price': 500, 'purchase_price': 200
            } # new
        ]
        InventoryService.process_inward(self.user, self.branch, items=items)
        
        self.assertEqual(BranchStock.objects.get(branch=self.branch, product=self.existing_product).quantity, 7)
        new_hat = Product.objects.get(product_code='NH-01')
        self.assertEqual(BranchStock.objects.get(branch=self.branch, product=new_hat).quantity, 5)

    def test_inward_failure_rollback(self):
        # Mixed payload where the second item fails due to negative quantity
        items = [
            {'barcode': 'BK-TST-EX1', 'quantity': 10},
            {'barcode': 'BK-TST-EX1', 'quantity': -5}, # invalid
        ]
        with self.assertRaises(ValueError):
            InventoryService.process_inward(self.user, self.branch, items=items)
            
        # The first item should roll back, meaning stock stays at 5
        stock = BranchStock.objects.get(branch=self.branch, product=self.existing_product)
        self.assertEqual(stock.quantity, 5)
