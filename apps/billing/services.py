from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils.timezone import now
from apps.inventory.models import SerializedItem, BranchStock, InventoryLog
from apps.billing.models import Cart, CartItem, Invoice, InvoiceItem
from apps.audit.services import AuditService

def generate_invoice_number(branch):
    # Extremely simple invoice generator for now
    count = Invoice.objects.filter(branch=branch).count() + 1
    return f"INV-{branch.code.upper()}-{count:06d}"

class TaxCalculationService:
    @staticmethod
    def get_applicable_gst_rate(product):
        """
        Priority 1: Product specific GST Rate
        Priority 2: HSN default GST Rate
        """
        if product.gst_rate and product.gst_rate.is_active:
            return product.gst_rate.rate_percentage
        if product.hsn_code and product.hsn_code.default_gst_rate and product.hsn_code.default_gst_rate.is_active:
            return product.hsn_code.default_gst_rate.rate_percentage
        
        raise ValueError("GST configuration is missing or inactive for this product.")

    @staticmethod
    def calculate_tax(selling_price, discount, gst_rate, is_inter_state=False):
        """
        Extracts GST and calculates taxable value from the final GST-inclusive price.
        Use Decimal for all calculations.
        """
        selling_price = Decimal(str(selling_price))
        discount = Decimal(str(discount))
        gst_rate = Decimal(str(gst_rate))

        final_price = selling_price - discount
        if final_price < Decimal('0.00'):
            raise ValueError("Final price cannot be negative.")

        # Taxable Value = Final Price / (1 + GST Rate / 100)
        taxable_value = final_price / (Decimal('1') + (gst_rate / Decimal('100')))
        taxable_value = taxable_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_gst = final_price - taxable_value

        result = {
            'final_selling_price': final_price,
            'taxable_amount': taxable_value,
            'cgst_rate': Decimal('0.00'),
            'cgst_amount': Decimal('0.00'),
            'sgst_rate': Decimal('0.00'),
            'sgst_amount': Decimal('0.00'),
            'igst_rate': Decimal('0.00'),
            'igst_amount': Decimal('0.00'),
            'total_gst_amount': total_gst,
            'final_line_total': final_price
        }

        if is_inter_state:
            result['igst_rate'] = gst_rate
            result['igst_amount'] = total_gst
        else:
            half_rate = (gst_rate / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            half_gst = (total_gst / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            result['cgst_rate'] = half_rate
            result['sgst_rate'] = half_rate
            
            # To avoid 1 cent discrepancy, we do SGST = total_gst - CGST
            result['cgst_amount'] = half_gst
            result['sgst_amount'] = total_gst - half_gst

        return result

class CartService:
    @staticmethod
    def get_or_create_active_cart(user, branch):
        cart, _ = Cart.objects.get_or_create(
            created_by=user, 
            branch=branch, 
            status='ACTIVE'
        )
        return cart

    @staticmethod
    def scan_barcode(user, branch, barcode):
        cart = CartService.get_or_create_active_cart(user, branch)
        
        with transaction.atomic():
            try:
                # Use select_for_update() inside atomic block to lock the row in PostgreSQL
                item = SerializedItem.objects.select_for_update().get(barcode=barcode, branch=branch)
            except SerializedItem.DoesNotExist:
                raise ValueError(f"Barcode {barcode} not found in this branch.")
                
            if item.status != 'IN_STOCK':
                raise ValueError(f"Item is {item.status}. Cannot add to cart.")
                
            # Soft reserve the item
            item.status = 'IN_CART'
            item.save()
            
            # Create Cart Item
            CartItem.objects.create(
                cart=cart,
                product=item.product,
                serialized_item=item,
                price=item.product.selling_price
            )
            
            # Update branch stock reserved quantity
            stock, _ = BranchStock.objects.get_or_create(branch=branch, product=item.product)
            stock.reserved_quantity += 1
            stock.save()

        return cart

    @staticmethod
    def remove_item(user, item_id):
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__created_by=user)
        except CartItem.DoesNotExist:
            raise ValueError("Cart item not found.")
            
        with transaction.atomic():
            item = cart_item.serialized_item
            item.status = 'IN_STOCK'
            item.save()
            
            stock = BranchStock.objects.get(branch=cart_item.cart.branch, product=cart_item.product)
            stock.reserved_quantity -= 1
            stock.save()
            
            cart_item.delete()

    @staticmethod
    def hold_cart(user, cart_id):
        try:
            cart = Cart.objects.get(id=cart_id, created_by=user, status='ACTIVE')
        except Cart.DoesNotExist:
            raise ValueError("Active cart not found.")
            
        if not cart.items.exists():
            raise ValueError("Cannot hold an empty cart.")
            
        cart.status = 'ON_HOLD'
        cart.save()
        return cart

    @staticmethod
    def resume_cart(user, cart_id):
        try:
            cart_to_resume = Cart.objects.get(id=cart_id, created_by=user, status='ON_HOLD')
        except Cart.DoesNotExist:
            raise ValueError("Held cart not found.")
            
        # If user has an ACTIVE cart, they can't resume another until they hold or clear the current one.
        active_cart = Cart.objects.filter(created_by=user, status='ACTIVE').first()
        if active_cart and active_cart.items.exists():
            raise ValueError("You must put your current active bill on hold before resuming another.")
            
        if active_cart and not active_cart.items.exists():
            # Just delete the empty active cart so they can resume
            active_cart.delete()
            
        cart_to_resume.status = 'ACTIVE'
        cart_to_resume.save()
        return cart_to_resume

class CheckoutService:
    @staticmethod
    @transaction.atomic
    def process_checkout(user, cart_id, payment_mode, customer_phone=None, customer_name=None):
        try:
            cart = Cart.objects.select_related('branch').get(id=cart_id, created_by=user)
        except Cart.DoesNotExist:
            raise ValueError("Cart not found.")
            
        # Lock the branch to prevent race conditions during invoice number generation
        from apps.branches.models import Branch
        locked_branch = Branch.objects.select_for_update().get(id=cart.branch_id)
            
        items = cart.items.select_related('product', 'serialized_item', 'product__hsn_code', 'product__gst_rate').all()
        if not items:
            raise ValueError("Cart is empty.")
            
        invoice = Invoice.objects.create(
            branch=cart.branch,
            invoice_number=generate_invoice_number(cart.branch),
            created_by=user,
            customer_phone=customer_phone or cart.customer_phone,
            customer_name=customer_name or cart.customer_name,
            total_taxable_amount=Decimal('0.00'),
            total_cgst=Decimal('0.00'),
            total_sgst=Decimal('0.00'),
            total_igst=Decimal('0.00'),
            grand_total=Decimal('0.00'),
            payment_mode=payment_mode
        )
        
        for item in items:
            product = item.product
            serial = item.serialized_item
            
            # Tax Calculation
            gst_rate_val = TaxCalculationService.get_applicable_gst_rate(product)
            tax_result = TaxCalculationService.calculate_tax(
                selling_price=item.price, 
                discount=Decimal('0.00'), 
                gst_rate=gst_rate_val, 
                is_inter_state=False
            )
            
            # Create Invoice Item
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                serialized_item=serial,
                product_name_snapshot=product.name,
                hsn_code_snapshot=product.hsn_code.code if product.hsn_code else '',
                gst_rate_snapshot=gst_rate_val,
                original_unit_price=product.selling_price,
                discount_amount=Decimal('0.00'),
                final_selling_price=tax_result['final_selling_price'],
                taxable_amount=tax_result['taxable_amount'],
                cgst_rate=tax_result['cgst_rate'],
                cgst_amount=tax_result['cgst_amount'],
                sgst_rate=tax_result['sgst_rate'],
                sgst_amount=tax_result['sgst_amount'],
                igst_rate=tax_result['igst_rate'],
                igst_amount=tax_result['igst_amount'],
                final_line_total=tax_result['final_line_total']
            )
            
            # Update Invoice Totals
            invoice.total_taxable_amount += tax_result['taxable_amount']
            invoice.total_cgst += tax_result['cgst_amount']
            invoice.total_sgst += tax_result['sgst_amount']
            invoice.total_igst += tax_result['igst_amount']
            invoice.grand_total += tax_result['final_line_total']
            
            # Update Inventory: Reserved - 1, Quantity - 1
            stock = BranchStock.objects.get(branch=cart.branch, product=product)
            stock.reserved_quantity -= 1
            stock.quantity -= 1
            stock.save()
            
            # Log OUTWARD
            InventoryLog.objects.create(
                branch=cart.branch,
                product=product,
                change_type='OUTWARD',
                quantity_change=-1,
                resulting_quantity=stock.quantity,
                reference_id=invoice.invoice_number,
                created_by=user
            )
            
            # Change serialized item status
            serial.status = 'SOLD'
            serial.save()
            
        invoice.save()
        
        # Clear Cart
        cart.delete()
        
        AuditService.log(
            user=user,
            action='CHECKOUT',
            module='BILLING',
            object_type='Invoice',
            object_id=invoice.invoice_number,
            new_value={'grand_total': str(invoice.grand_total), 'items_count': len(items)}
        )
        
        return invoice

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

class ReceiptPrinterService:
    @staticmethod
    def generate_receipt_pdf(invoice):
        buffer = BytesIO()
        
        # 80mm thermal receipt
        width = 80 * mm
        # Height is dynamic based on items, we'll set a long length and the frontend/printer handles cut
        height = 200 * mm 
        
        c = canvas.Canvas(buffer, pagesize=(width, height))
        
        y = height - 10 * mm
        
        # Header
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2.0, y, "BRAND KING")
        y -= 6 * mm
        
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2.0, y, f"Branch: {invoice.branch.name}")
        y -= 4 * mm
        c.drawCentredString(width / 2.0, y, f"GSTIN: {invoice.branch.code}123456789")
        y -= 8 * mm
        
        # Details
        c.setFont("Helvetica", 8)
        c.drawString(4 * mm, y, f"Invoice No: {invoice.invoice_number}")
        y -= 4 * mm
        c.drawString(4 * mm, y, f"Date: {invoice.created_at.strftime('%Y-%m-%d %H:%M')}")
        y -= 4 * mm
        c.drawString(4 * mm, y, f"Cashier: {invoice.created_by.first_name}")
        y -= 8 * mm
        
        if invoice.customer_phone:
            c.drawString(4 * mm, y, f"Customer: {invoice.customer_phone}")
            y -= 6 * mm
            
        c.line(2 * mm, y, width - 2 * mm, y)
        y -= 4 * mm
        
        # Items Header
        c.setFont("Helvetica-Bold", 7)
        c.drawString(4 * mm, y, "Item")
        c.drawString(45 * mm, y, "Qty")
        c.drawString(55 * mm, y, "Price")
        c.drawString(70 * mm, y, "Total")
        y -= 4 * mm
        c.line(2 * mm, y, width - 2 * mm, y)
        y -= 6 * mm
        
        # Items
        c.setFont("Helvetica", 7)
        for item in invoice.items.all():
            name = item.product_name_snapshot[:20]
            c.drawString(4 * mm, y, name)
            c.drawString(45 * mm, y, "1")
            c.drawString(55 * mm, y, f"{item.final_selling_price}")
            c.drawString(70 * mm, y, f"{item.final_line_total}")
            y -= 4 * mm
            
        y -= 2 * mm
        c.line(2 * mm, y, width - 2 * mm, y)
        y -= 6 * mm
        
        # Totals
        c.setFont("Helvetica-Bold", 8)
        c.drawString(30 * mm, y, "Grand Total:")
        c.drawString(60 * mm, y, f"Rs {invoice.grand_total}")
        y -= 6 * mm
        
        c.setFont("Helvetica", 7)
        c.drawString(30 * mm, y, f"Payment Mode: {invoice.payment_mode}")
        y -= 8 * mm
        
        # Footer
        c.setFont("Helvetica", 7)
        c.drawCentredString(width / 2.0, y, "Thank you for shopping with us!")
        
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer
