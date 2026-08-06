from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.branches.models import Branch
from apps.products.models import Product, ProductType, Category, Brand, HSNCode, GSTRate
from apps.inventory.models import SerializedItem, BranchStock
from .models import Cart, Invoice

class POSBillingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(email='admin@test.com', password='password', role='ADMIN')
        
        self.branch = Branch.objects.create(
            name='Test Branch',
            code='TB01',
            address='Test Address',
            contact_number='1234567890'
        )
        self.admin.branch = self.branch
        self.admin.save()
        self.client.force_authenticate(user=self.admin)
        
        self.pt = ProductType.objects.create(name='Regular', code='REG')
        self.cat = Category.objects.create(name='Shirts', code='SHRT')
        self.brand = Brand.objects.create(name='Nike', code='NIKE')
        self.gst = GSTRate.objects.create(rate_percentage='18.00', effective_from='2026-01-01')
        self.hsn = HSNCode.objects.create(code='6109', description='T-shirts', effective_from='2026-01-01', default_gst_rate=self.gst)

        self.product = Product.objects.create(
            name='Red Nike Shirt',
            product_code='RN-01',
            sku='SKU-RN-01',
            category=self.cat,
            brand=self.brand,
            product_type=self.pt,
            hsn_code=self.hsn,
            gst_rate=self.gst,
            mrp='1500.00',
            selling_price='1000.00',
            purchase_price='500.00'
        )
        
        self.stock = BranchStock.objects.create(branch=self.branch, product=self.product, quantity=2)
        
        self.item1 = SerializedItem.objects.create(
            product=self.product,
            branch=self.branch,
            barcode='ITEM-001',
            status='IN_STOCK'
        )
        self.item2 = SerializedItem.objects.create(
            product=self.product,
            branch=self.branch,
            barcode='ITEM-002',
            status='IN_STOCK'
        )

    def test_scan_item(self):
        res = self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-001'})
        self.assertEqual(res.status_code, 200)
        
        # Check stock is reserved
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 1)
        
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.status, 'IN_CART')
        
    def test_scan_already_in_cart(self):
        self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-001'})
        res = self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-001'})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Cannot add to cart", res.json()['message'])
        
    def test_hold_and_resume_cart(self):
        # 1. Scan item
        self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-001'})
        cart = Cart.objects.get(created_by=self.admin, status='ACTIVE')
        
        # 2. Hold cart
        res = self.client.post('/api/billing/cart/hold/', {'cart_id': str(cart.id)})
        self.assertEqual(res.status_code, 200)
        cart.refresh_from_db()
        self.assertEqual(cart.status, 'ON_HOLD')
        
        # 3. Scan for next customer
        self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-002'})
        active_cart = Cart.objects.get(created_by=self.admin, status='ACTIVE')
        self.assertEqual(active_cart.items.count(), 1)
        self.assertNotEqual(cart.id, active_cart.id)
        
        # 4. Try resume while active is not empty
        res = self.client.post(f'/api/billing/cart/{cart.id}/resume/')
        self.assertEqual(res.status_code, 400)
        
        # 5. Hold second cart and resume first
        self.client.post('/api/billing/cart/hold/', {'cart_id': str(active_cart.id)})
        res = self.client.post(f'/api/billing/cart/{cart.id}/resume/')
        self.assertEqual(res.status_code, 200)
        cart.refresh_from_db()
        self.assertEqual(cart.status, 'ACTIVE')
        
    def test_checkout(self):
        self.client.post('/api/billing/cart/scan/', {'barcode': 'ITEM-001'})
        cart = Cart.objects.get(created_by=self.admin, status='ACTIVE')
        
        res = self.client.post('/api/billing/cart/checkout/', {
            'cart_id': str(cart.id),
            'payment_mode': 'CASH',
            'customer_phone': '9876543210'
        })
        self.assertEqual(res.status_code, 200)
        
        invoice = Invoice.objects.first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.grand_total, 1000)
        
        # Check item sold
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.status, 'SOLD')
        
        # Check stock deducted
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 1)
        self.assertEqual(self.stock.reserved_quantity, 0)
