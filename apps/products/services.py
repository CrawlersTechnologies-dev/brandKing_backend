import pandas as pd
from decimal import Decimal
from django.db import transaction
from .models import Product, ProductType, Category, Brand, GSTRate, HSNCode
from apps.barcodes.services import BarcodeService
from apps.audit.services import AuditService
import io

class BulkImportService:
    EXPECTED_COLUMNS = [
        'product_name', 'product_image', 'product_code', 'sku', 'category', 'brand',
        'product_type', 'hsn_code', 'gst_rate', 'mrp', 'selling_price', 'purchase_price',
        'barcode', 'description'
    ]

    @staticmethod
    def _parse_file(file_obj):
        file_name = file_obj.name.lower()
        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            if file_name.endswith('.csv'):
                df = pd.read_csv(file_obj, dtype=str)
            elif file_name.endswith('.xlsx'):
                df = pd.read_excel(file_obj, dtype=str)
            else:
                raise ValueError("Unsupported file format. Please upload a CSV or XLSX file.")
            
            # Fill NaNs with empty string
            df = df.fillna('')
            # Strip whitespace from column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            return df
        except Exception as e:
            raise ValueError(f"Error parsing file: {str(e)}")

    @staticmethod
    def validate_file(file_obj):
        df = BulkImportService._parse_file(file_obj)
        
        # Check required columns
        missing_cols = set(BulkImportService.EXPECTED_COLUMNS) - set(df.columns)
        if 'product image' in df.columns and 'product_image' not in df.columns:
            df.rename(columns={'product image': 'product_image'}, inplace=True)
            missing_cols = set(BulkImportService.EXPECTED_COLUMNS) - set(df.columns)
            
        if missing_cols:
            raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

        errors = []
        valid_rows = 0
        invalid_rows = 0
        
        # Pre-fetch lookup dictionaries (case-insensitive keys)
        product_types = {pt.name.strip().lower(): pt for pt in ProductType.objects.filter(is_active=True)}
        categories = {c.name.strip().lower(): c for c in Category.objects.filter(is_active=True)}
        brands = {b.name.strip().lower(): b for b in Brand.objects.filter(is_active=True)}
        hsn_codes = {h.code.strip().lower(): h for h in HSNCode.objects.filter(is_active=True)}
        # gst_rates expects formats like '18', '18%', '18.00'
        gst_rates = {}
        for g in GSTRate.objects.filter(is_active=True):
            val = str(g.rate_percentage).rstrip('0').rstrip('.')
            gst_rates[val] = g

        # Fetch existing unique fields
        existing_product_codes = set(Product.objects.values_list('product_code', flat=True))
        existing_skus = set(Product.objects.exclude(sku__isnull=True).exclude(sku="").values_list('sku', flat=True))
        existing_barcodes = set(Product.objects.exclude(barcode__isnull=True).exclude(barcode="").values_list('barcode', flat=True))

        # Local duplicates tracker
        local_codes = set()
        local_skus = set()
        local_barcodes = set()

        for idx, row in df.iterrows():
            row_num = idx + 2 # Excel row number (header is 1)
            row_errors = []

            # 1. Empty Check
            product_name = str(row.get('product_name', '')).strip()
            if not product_name:
                row_errors.append({'field': 'product_name', 'error': 'Product name cannot be empty.'})
                continue # Skip processing empty rows completely

            # 2. Unique fields validation
            p_code = str(row.get('product_code', '')).strip()
            if not p_code:
                row_errors.append({'field': 'product_code', 'error': 'Product code cannot be empty.'})
            else:
                if p_code in local_codes:
                    row_errors.append({'field': 'product_code', 'error': 'Duplicate product_code in uploaded file.'})
                elif p_code in existing_product_codes:
                    row_errors.append({'field': 'product_code', 'error': 'Product code already exists in database.'})
                local_codes.add(p_code)

            sku = str(row.get('sku', '')).strip()
            if sku:
                if sku in local_skus:
                    row_errors.append({'field': 'sku', 'error': 'Duplicate sku in uploaded file.'})
                elif sku in existing_skus:
                    row_errors.append({'field': 'sku', 'error': 'SKU already exists in database.'})
                local_skus.add(sku)

            barcode = str(row.get('barcode', '')).strip()
            if barcode:
                if barcode in local_barcodes:
                    row_errors.append({'field': 'barcode', 'error': 'Duplicate barcode in uploaded file.'})
                elif barcode in existing_barcodes:
                    row_errors.append({'field': 'barcode', 'error': 'Barcode already exists in database.'})
                local_barcodes.add(barcode)

            # 3. Financial validations
            for price_field in ['mrp', 'selling_price', 'purchase_price']:
                val = str(row.get(price_field, '')).strip()
                if not val:
                    row_errors.append({'field': price_field, 'error': f'{price_field} cannot be empty.'})
                else:
                    try:
                        d_val = Decimal(val)
                        if d_val < 0:
                            row_errors.append({'field': price_field, 'error': f'{price_field} must be >= 0.'})
                    except:
                        row_errors.append({'field': price_field, 'error': f'Invalid numeric value for {price_field}.'})

            # 4. Master Lookups
            # Product Type
            pt_name = str(row.get('product_type', '')).strip().lower()
            if not pt_name or pt_name not in product_types:
                row_errors.append({'field': 'product_type', 'error': 'Invalid or inactive product type.'})
            
            # HSN
            hsn = str(row.get('hsn_code', '')).strip().lower()
            if not hsn or hsn not in hsn_codes:
                row_errors.append({'field': 'hsn_code', 'error': 'HSN code does not exist or is inactive.'})

            # GST Rate
            gst = str(row.get('gst_rate', '')).strip().replace('%', '')
            try:
                gst_val = str(Decimal(gst)).rstrip('0').rstrip('.') if gst else None
                if not gst_val or gst_val not in gst_rates:
                    row_errors.append({'field': 'gst_rate', 'error': 'GST rate does not exist or is inactive.'})
            except:
                row_errors.append({'field': 'gst_rate', 'error': 'Invalid GST rate.'})

            # Category
            cat = str(row.get('category', '')).strip().lower()
            if cat and cat not in categories:
                row_errors.append({'field': 'category', 'error': 'Category does not exist.'})

            # Brand
            brd = str(row.get('brand', '')).strip().lower()
            if brd and brd not in brands:
                row_errors.append({'field': 'brand', 'error': 'Brand does not exist.'})

            if row_errors:
                for err in row_errors:
                    err['row'] = row_num
                    err['value'] = str(row.get(err['field'], ''))
                    errors.append(err)
                invalid_rows += 1
            else:
                valid_rows += 1

        return {
            'total_rows': valid_rows + invalid_rows,
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows,
            'errors': errors
        }

    @staticmethod
    @transaction.atomic
    def confirm_import(file_obj, user, import_only_valid=False):
        df = BulkImportService._parse_file(file_obj)
        if 'product image' in df.columns:
            df.rename(columns={'product image': 'product_image'}, inplace=True)
            
        validation = BulkImportService.validate_file(file_obj)
        
        if not import_only_valid and validation['invalid_rows'] > 0:
            raise ValueError(f"File contains {validation['invalid_rows']} invalid rows. Cannot proceed unless import_only_valid is true.")

        # Re-fetch lookups
        product_types = {pt.name.strip().lower(): pt for pt in ProductType.objects.filter(is_active=True)}
        categories = {c.name.strip().lower(): c for c in Category.objects.filter(is_active=True)}
        brands = {b.name.strip().lower(): b for b in Brand.objects.filter(is_active=True)}
        hsn_codes = {h.code.strip().lower(): h for h in HSNCode.objects.filter(is_active=True)}
        gst_rates = {}
        for g in GSTRate.objects.filter(is_active=True):
            val = str(g.rate_percentage).rstrip('0').rstrip('.')
            gst_rates[val] = g
            
        invalid_rows_set = set(err['row'] for err in validation['errors'])
        
        products_to_create = []
        successful_count = 0

        for idx, row in df.iterrows():
            row_num = idx + 2
            
            # Skip empty product names completely
            if not str(row.get('product_name', '')).strip():
                continue
                
            if row_num in invalid_rows_set:
                continue
                
            pt_name = str(row.get('product_type', '')).strip().lower()
            hsn = str(row.get('hsn_code', '')).strip().lower()
            gst = str(row.get('gst_rate', '')).strip().replace('%', '')
            gst_val = str(Decimal(gst)).rstrip('0').rstrip('.')
            cat = str(row.get('category', '')).strip().lower()
            brd = str(row.get('brand', '')).strip().lower()
            barcode = str(row.get('barcode', '')).strip()

            if not barcode:
                barcode = BarcodeService.generate_proprietary_barcode(None)

            sku = str(row.get('sku', '')).strip() or None

            product = Product(
                name=str(row.get('product_name', '')).strip(),
                product_code=str(row.get('product_code', '')).strip(),
                sku=sku,
                barcode=barcode,
                category=categories.get(cat) if cat else None,
                brand=brands.get(brd) if brd else None,
                product_type=product_types[pt_name],
                description=str(row.get('description', '')).strip(),
                hsn_code=hsn_codes[hsn],
                gst_rate=gst_rates[gst_val],
                mrp=Decimal(str(row.get('mrp', '')).strip()),
                selling_price=Decimal(str(row.get('selling_price', '')).strip()),
                purchase_price=Decimal(str(row.get('purchase_price', '')).strip()),
                created_by=user
            )
            products_to_create.append(product)
            successful_count += 1

        Product.objects.bulk_create(products_to_create)
        
        # Generate Audit Log
        AuditService.log(
            user=user,
            action='BULK_PRODUCT_IMPORT',
            module='PRODUCT_MANAGEMENT',
            object_type='Product',
            object_id='BULK',
            new_value={
                'total_rows': validation['total_rows'],
                'successful_products': successful_count,
                'failed_rows': validation['invalid_rows']
            }
        )

        return successful_count, validation['invalid_rows']
