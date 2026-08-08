import uuid
from .models import BarcodeSequence

class BarcodeService:
    @staticmethod
    def generate_proprietary_barcode(branch_code=None):
        """
        Generates a unique proprietary barcode in BK000001 format.
        """
        seq = BarcodeSequence.get_next_value()
        return f"BK{seq:06d}"

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128

class LabelPrinterService:
    @staticmethod
    def generate_labels_pdf(serialized_items, include_selling_price=False):
        buffer = BytesIO()
        
        # 50mm x 25mm thermal label
        width = 50 * mm
        height = 25 * mm
        
        c = canvas.Canvas(buffer, pagesize=(width, height))
        
        for item in serialized_items:
            product = item.product
            # Draw Logo (Text for now)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(2 * mm, height - 4 * mm, "BRAND KING")
            
            # Product Name
            c.setFont("Helvetica", 5)
            name = product.name[:25] # truncate if too long
            c.drawString(2 * mm, height - 7 * mm, name)
            
            # SKU / Code
            c.drawString(2 * mm, height - 10 * mm, f"SKU: {product.product_code}")
            
            # Barcode
            barcode_str = item.barcode
            barcode = code128.Code128(barcode_str, barHeight=6*mm, barWidth=0.25*mm)
            # Position barcode
            barcode.drawOn(c, 2 * mm, height - 17 * mm)
            
            # Text under barcode
            c.setFont("Helvetica", 4)
            c.drawString(2 * mm, height - 20 * mm, barcode_str)
            
            # MRP / Selling Price
            c.setFont("Helvetica-Bold", 5)
            price_text = f"MRP: Rs {product.mrp}"
            if include_selling_price:
                price_text += f" | SP: Rs {product.selling_price}"
            c.drawString(2 * mm, height - 23 * mm, price_text)
            
            c.showPage()
            
        c.save()
        buffer.seek(0)
        return buffer

