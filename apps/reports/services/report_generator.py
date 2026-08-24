from decimal import Decimal
from django.db.models import Sum, Count, F
from django.utils import timezone
from apps.billing.models import Invoice, InvoiceItem, ExchangeRequest
from apps.inventory.models import BranchStock
from apps.reports.models import Expense
from django.db.models.functions import TruncDay, TruncMonth

class ReportGenerator:
    @staticmethod
    def get_daily_sales(start_date, end_date, branch_id=None):
        qs = Invoice.objects.filter(created_at__range=[start_date, end_date])
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        data = qs.annotate(date=TruncDay('created_at')).values('date').annotate(
            total_revenue=Sum('grand_total'),
            total_invoices=Count('id'),
            total_cgst=Sum('total_cgst'),
            total_sgst=Sum('total_sgst'),
            total_igst=Sum('total_igst')
        ).order_by('date')
        
        return list(data)

    @staticmethod
    def get_monthly_sales(start_date, end_date, branch_id=None):
        qs = Invoice.objects.filter(created_at__range=[start_date, end_date])
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        data = qs.annotate(month=TruncMonth('created_at')).values('month').annotate(
            total_revenue=Sum('grand_total'),
            total_invoices=Count('id')
        ).order_by('month')
        
        return list(data)

    @staticmethod
    def get_stock_report(branch_id=None):
        qs = BranchStock.objects.all().select_related('product', 'branch')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        data = []
        for stock in qs:
            data.append({
                'branch': stock.branch.name if stock.branch else 'Unknown',
                'product_name': stock.product.name,
                'product_code': stock.product.product_code,
                'quantity': stock.quantity,
                'purchase_price': float(stock.product.purchase_price or 0.0),
                'total_valuation': float((stock.product.purchase_price or 0.0) * stock.quantity)
            })
        return data

    @staticmethod
    def get_expense_report(start_date, end_date, branch_id=None):
        qs = Expense.objects.filter(date__range=[start_date.date(), end_date.date()])
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        return list(qs.values('date', 'branch__name', 'category', 'amount', 'recorded_by__first_name', 'notes'))

    @staticmethod
    def get_profit_summary(start_date, end_date, branch_id=None):
        invoices = Invoice.objects.filter(created_at__range=[start_date, end_date])
        expenses = Expense.objects.filter(date__range=[start_date.date(), end_date.date()])
        
        if branch_id:
            invoices = invoices.filter(branch_id=branch_id)
            expenses = expenses.filter(branch_id=branch_id)
            
        total_revenue = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Calculate Cost of Goods Sold (COGS)
        items = InvoiceItem.objects.filter(invoice__in=invoices)
        cogs = Decimal('0.00')
        for item in items:
            cogs += (item.purchase_price_snapshot or Decimal('0.00'))
            
        net_profit = total_revenue - total_expenses - cogs
        
        return {
            'total_revenue': float(total_revenue),
            'cost_of_goods_sold': float(cogs),
            'gross_profit': float(total_revenue - cogs),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit)
        }

    @staticmethod
    def get_gst_report(start_date, end_date, branch_id=None):
        qs = Invoice.objects.filter(created_at__range=[start_date, end_date])
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        data = qs.values('invoice_number', 'created_at', 'grand_total', 'total_cgst', 'total_sgst', 'total_igst')
        return list(data)

    @staticmethod
    def get_returns_report(start_date, end_date, branch_id=None):
        qs = ExchangeRequest.objects.filter(created_at__range=[start_date, end_date])
        if branch_id:
            qs = qs.filter(invoice__branch_id=branch_id)
            
        data = qs.values('id', 'invoice__invoice_number', 'status', 'created_at', 'approved_by__first_name')
        return list(data)

    @staticmethod
    def get_cashier_sales(start_date, end_date, branch_id=None):
        qs = Invoice.objects.filter(created_at__range=[start_date, end_date])
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            
        data = qs.values('created_by__first_name', 'created_by__last_name').annotate(
            total_revenue=Sum('grand_total'),
            total_invoices=Count('id')
        ).order_by('-total_revenue')
        return list(data)
