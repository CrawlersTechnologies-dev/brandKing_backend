import io
import pandas as pd
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from apps.accounts.models import User
from apps.products.models import Product, ProductType, Category, Brand, HSNCode, GSTRate, TemporaryBulkUpload
from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient

class BulkProductImportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(email='admin@test.com', password='password', role='ADMIN')
        self.client.force_authenticate(user=self.admin)
        
        # Setup Masters
        self.pt = ProductType.objects.create(name='Regular', code='REG')
        self.cat = Category.objects.create(name='Shirts', code='SHRT')
        self.brand = Brand.objects.create(name='Nike', code='NK')
        self.gst = GSTRate.objects.create(name='18%', rate_percentage=Decimal('18.00'), effective_from=date(2026, 1, 1))
        self.hsn = HSNCode.objects.create(code='6109', default_gst_rate=self.gst, effective_from=date(2026, 1, 1))

    def create_test_csv(self, data):
        df = pd.DataFrame(data)
        out = io.BytesIO()
        df.to_csv(out, index=False)
        out.seek(0)
        out.name = 'test.csv'
        return out

    def test_get_template(self):
        res = self.client.get('/api/products/bulk-upload/template/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_validate_valid_csv(self):
        csv_file = self.create_test_csv([{
            'product_name': 'Test Shirt',
            'product_image': '',
            'product_code': 'TS-01',
            'sku': 'SKU-01',
            'category': 'Shirts',
            'brand': 'Nike',
            'product_type': 'Regular',
            'hsn_code': '6109',
            'gst_rate': '18',
            'mrp': '1000.00',
            'selling_price': '900.00',
            'purchase_price': '500.00',
            'barcode': '',
            'description': 'Test desc'
        }])
        
        res = self.client.post('/api/products/bulk-upload/validate/', {'file': csv_file})
        self.assertEqual(res.status_code, 200)
        
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['total_rows'], 1)
        self.assertEqual(data['data']['invalid_rows'], 0)
        self.assertTrue('file_id' in data['data'])

    def test_validate_invalid_csv(self):
        csv_file = self.create_test_csv([{
            'product_name': 'Test Shirt 2',
            'product_image': '',
            'product_code': 'TS-02',
            'sku': 'SKU-02',
            'category': 'NonExistent', # Invalid category
            'brand': 'Nike',
            'product_type': 'FakeType', # Invalid type
            'hsn_code': '6109',
            'gst_rate': '99', # Invalid GST
            'mrp': '-100', # Negative price
            'selling_price': '900.00',
            'purchase_price': '500.00',
            'barcode': '',
            'description': 'Test desc'
        }])
        
        res = self.client.post('/api/products/bulk-upload/validate/', {'file': csv_file})
        self.assertEqual(res.status_code, 200)
        
        data = res.json()['data']
        self.assertEqual(data['invalid_rows'], 1)
        self.assertGreater(len(data['errors']), 0)

    def test_confirm_import_valid(self):
        # 1. Validate
        csv_file = self.create_test_csv([{
            'product_name': 'Test Shirt 3',
            'product_image': '',
            'product_code': 'TS-03',
            'sku': 'SKU-03',
            'category': 'Shirts',
            'brand': 'Nike',
            'product_type': 'Regular',
            'hsn_code': '6109',
            'gst_rate': '18',
            'mrp': '1000.00',
            'selling_price': '900.00',
            'purchase_price': '500.00',
            'barcode': '',
            'description': 'Test desc'
        }])
        val_res = self.client.post('/api/products/bulk-upload/validate/', {'file': csv_file})
        file_id = val_res.json()['data']['file_id']
        
        # 2. Confirm
        conf_res = self.client.post('/api/products/bulk-upload/confirm/', {'file_id': file_id})
        if conf_res.status_code != 200:
            print("CONFIRM ERROR:", conf_res.json())
        self.assertEqual(conf_res.status_code, 200)
        
        # 3. Verify
        p = Product.objects.get(product_code='TS-03')
        self.assertEqual(p.name, 'Test Shirt 3')
        self.assertIsNotNone(p.barcode) # Generated automatically
        self.assertEqual(p.category.name, 'Shirts')
