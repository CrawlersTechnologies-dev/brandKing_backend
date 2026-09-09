from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from common.responses import success_response, error_response
from apps.billing.models import Invoice
from apps.branches.models import Counter
from django.db.models import Sum, Count
from decimal import Decimal

class RevenueReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branch = request.user.branch
        branch_id = request.query_params.get('branch_id')
        
        invoices = Invoice.objects.all()
        if branch_id:
            invoices = invoices.filter(branch_id=branch_id)
        elif branch:
            invoices = invoices.filter(branch=branch)
        
        total_revenue = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        total_sales = invoices.count()
        
        # Counter-wise
        counters_data = invoices.values('counter__name').annotate(
            revenue=Sum('grand_total'),
            transactions=Count('id')
        ).order_by('counter__name')
        
        counter_wise = {}
        for c in counters_data:
            name = c['counter__name'] or 'Unknown Counter'
            counter_wise[name] = {
                'revenue': str(c['revenue'] or '0.00'),
                'transactions': c['transactions']
            }
            
        # Cashier-wise
        cashiers_data = invoices.values('created_by__first_name', 'created_by__last_name').annotate(
            revenue=Sum('grand_total'),
            transactions=Count('id')
        )
        
        cashier_wise = {}
        for c in cashiers_data:
            first = c['created_by__first_name'] or ''
            last = c['created_by__last_name'] or ''
            name = f"{first} {last}".strip() or 'Unknown Cashier'
            cashier_wise[name] = {
                'revenue': str(c['revenue'] or '0.00'),
                'transactions': c['transactions']
            }
            
        # Payment modes
        payment_data = invoices.values('payment_mode').annotate(
            total=Sum('grand_total')
        )
        
        payment_methods = {}
        for p in payment_data:
            mode = p['payment_mode'] or 'Unknown'
            payment_methods[mode] = str(p['total'] or '0.00')
            
        data = {
            'overall_revenue': str(total_revenue),
            'total_sales': total_sales,
            'counter_wise': counter_wise,
            'cashier_wise': cashier_wise,
            'returns_and_refunds': 0, # Placeholder for future implementation
            'payment_methods': payment_methods
        }
        
        return success_response(data=data, message="Revenue report fetched successfully")

from django.utils import timezone
from datetime import timedelta
from apps.branches.models import Branch
from apps.accounts.models import User
from apps.products.models import Product
from apps.inventory.models import BranchStock
from apps.billing.models import InvoiceItem, Offer, ExchangeRequest
from apps.audit.models import AuditLog
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.db.models import F

class GlobalDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'ADMIN':
            return error_response(message="Access Denied. Global Admin only.", status=403)
            
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        interval = request.query_params.get('interval', 'daily').lower()
        
        end_date = timezone.now()
        if end_date_str:
            from django.utils.dateparse import parse_date
            parsed_end = parse_date(end_date_str)
            if parsed_end:
                end_date = timezone.make_aware(timezone.datetime.combine(parsed_end, timezone.datetime.max.time()))
                
        start_date = end_date - timedelta(days=30)
        if start_date_str:
            from django.utils.dateparse import parse_date
            parsed_start = parse_date(start_date_str)
            if parsed_start:
                start_date = timezone.make_aware(timezone.datetime.combine(parsed_start, timezone.datetime.min.time()))

        # A. Summary Cards
        total_branches = Branch.objects.filter(is_active=True).count()
        total_employees = User.objects.filter(is_active=True).count()
        total_products = Product.objects.count()
        
        invoices = Invoice.objects.filter(created_at__range=[start_date, end_date])
        revenue = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        gst_agg = invoices.aggregate(c=Sum('total_cgst'), s=Sum('total_sgst'), i=Sum('total_igst'))
        gst_collection = (gst_agg['c'] or Decimal('0.00')) + (gst_agg['s'] or Decimal('0.00')) + (gst_agg['i'] or Decimal('0.00'))
        
        # B. Sales Trend (Recharts)
        trunc_func = TruncDay('created_at')
        if interval == 'weekly':
            trunc_func = TruncWeek('created_at')
        elif interval == 'monthly':
            trunc_func = TruncMonth('created_at')
            
        trend_data = invoices.annotate(date=trunc_func).values('date').annotate(
            revenue=Sum('grand_total')
        ).order_by('date')
        
        sales_trend = []
        for t in trend_data:
            if t['date']:
                sales_trend.append({
                    'date': t['date'].strftime('%Y-%m-%d'),
                    'revenue': str(t['revenue'] or '0.00')
                })
                
        # C. Branch Performance
        branch_data = invoices.values('branch__name').annotate(
            revenue=Sum('grand_total')
        ).order_by('-revenue')
        
        branch_performance = []
        for b in branch_data:
            branch_performance.append({
                'branch_name': b['branch__name'] or 'Unknown',
                'revenue': str(b['revenue'] or '0.00')
            })
            
        # D. Recent Activities
        logs = AuditLog.objects.order_by('-timestamp')[:5]
        recent_activities = []
        for log in logs:
            action = f"{log.action} {log.object_type}"
            msg = f"{action} by {log.user.first_name if log.user else 'System'}"
            recent_activities.append({
                'message': msg,
                'time_ago': log.timestamp.strftime('%Y-%m-%d %H:%M')
            })
            
        # Pending Approvals
        pending_approvals = []
        unapproved_users = User.objects.filter(is_approved=False)[:5]
        for u in unapproved_users:
            pending_approvals.append({
                'type': 'Employee Creation',
                'details': f"{u.first_name or u.email} ({u.role})",
                'id': str(u.id)
            })
            
        draft_offers = Offer.objects.filter(status='DRAFT')[:5]
        for o in draft_offers:
            pending_approvals.append({
                'type': 'Offer Request',
                'details': o.name,
                'id': str(o.id)
            })
            
        pending_returns = ExchangeRequest.objects.filter(status='PENDING')[:5]
        for r in pending_returns:
            pending_approvals.append({
                'type': 'Return Approval',
                'details': r.invoice.invoice_number if r.invoice else str(r.id),
                'id': str(r.id)
            })
            
        # E. Top Products
        from django.db.models import Count
        top_items = InvoiceItem.objects.filter(invoice__created_at__range=[start_date, end_date])\
            .values('product_name_snapshot')\
            .annotate(total_sold=Count('id'))\
            .order_by('-total_sold')[:5]
            
        top_products = []
        for item in top_items:
            top_products.append({
                'product_name': item['product_name_snapshot'],
                'total_sold': item['total_sold']
            })
            
        # F. Low Stock Alerts
        low_stocks = BranchStock.objects.filter(quantity__lt=10).select_related('product', 'branch')[:10]
        low_stock_alerts = []
        for ls in low_stocks:
            low_stock_alerts.append({
                'product_name': ls.product.name,
                'branch_name': ls.branch.name,
                'quantity_left': ls.quantity
            })
            
        data = {
            'summary_cards': {
                'total_branches': total_branches,
                'total_employees': total_employees,
                'total_products': total_products,
                'revenue': str(revenue),
                'gst_collection': str(gst_collection)
            },
            'sales_trend': sales_trend,
            'branch_performance': branch_performance,
            'recent_activities': recent_activities,
            'pending_approvals': pending_approvals,
            'top_products': top_products,
            'low_stock_alerts': low_stock_alerts
        }
        
        return success_response(data=data, message="Dashboard data fetched successfully.")

class SubAdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'SUB_ADMIN':
            return error_response(message="Access Denied. Sub-Admin only.", status=403)

        branch_id = request.user.branch_id
        if not branch_id:
            return error_response(message="Sub-Admin is not assigned to any branch.", status=400)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        interval = request.query_params.get('interval', 'daily').lower()

        end_date = timezone.now()
        if end_date_str:
            from django.utils.dateparse import parse_date
            parsed_end = parse_date(end_date_str)
            if parsed_end:
                end_date = timezone.make_aware(timezone.datetime.combine(parsed_end, timezone.datetime.max.time()))

        start_date = end_date - timedelta(days=30)
        if start_date_str:
            from django.utils.dateparse import parse_date
            parsed_start = parse_date(start_date_str)
            if parsed_start:
                start_date = timezone.make_aware(timezone.datetime.combine(parsed_start, timezone.datetime.min.time()))

        # A. Summary Cards
        total_employees = User.objects.filter(is_active=True, branch_id=branch_id).count()
        total_products = BranchStock.objects.filter(branch_id=branch_id, quantity__gt=0).count()

        invoices = Invoice.objects.filter(branch_id=branch_id, created_at__range=[start_date, end_date])
        revenue = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        gst_agg = invoices.aggregate(c=Sum('total_cgst'), s=Sum('total_sgst'), i=Sum('total_igst'))
        gst_collection = (gst_agg['c'] or Decimal('0.00')) + (gst_agg['s'] or Decimal('0.00')) + (gst_agg['i'] or Decimal('0.00'))

        # B. Sales Trend (Recharts)
        trunc_func = TruncDay('created_at')
        if interval == 'weekly':
            trunc_func = TruncWeek('created_at')
        elif interval == 'monthly':
            trunc_func = TruncMonth('created_at')

        trend_data = invoices.annotate(date=trunc_func).values('date').annotate(
            revenue=Sum('grand_total')
        ).order_by('date')

        sales_trend = []
        for t in trend_data:
            if t['date']:
                sales_trend.append({
                    'date': t['date'].strftime('%Y-%m-%d'),
                    'revenue': str(t['revenue'] or '0.00')
                })

        # D. Recent Activities
        logs = AuditLog.objects.filter(user__branch_id=branch_id).order_by('-timestamp')[:5]
        recent_activities = []
        for log in logs:
            action = f"{log.action} {log.object_type}"
            msg = f"{action} by {log.user.first_name if log.user else 'System'}"
            recent_activities.append({
                'message': msg,
                'time_ago': log.timestamp.strftime('%Y-%m-%d %H:%M')
            })

        # E. Top Products
        from django.db.models import Count
        top_items = InvoiceItem.objects.filter(invoice__branch_id=branch_id, invoice__created_at__range=[start_date, end_date])\
            .values('product_name_snapshot')\
            .annotate(total_sold=Count('id'))\
            .order_by('-total_sold')[:5]

        top_products = []
        for item in top_items:
            top_products.append({
                'product_name': item['product_name_snapshot'],
                'total_sold': item['total_sold']
            })

        # F. Low Stock Alerts
        low_stocks = BranchStock.objects.filter(branch_id=branch_id, quantity__lt=10).select_related('product')[:10]
        low_stock_alerts = []
        for ls in low_stocks:
            low_stock_alerts.append({
                'product_name': ls.product.name,
                'quantity_left': ls.quantity
            })
            
        pending_returns = ExchangeRequest.objects.filter(status='PENDING', invoice__branch_id=branch_id)[:5]
        pending_approvals = []
        for r in pending_returns:
            pending_approvals.append({
                'type': 'Return Approval',
                'details': r.invoice.invoice_number if r.invoice else str(r.id),
                'id': str(r.id)
            })

        data = {
            'branch_name': request.user.branch.name if request.user.branch else None,
            'summary_cards': {
                'total_employees': total_employees,
                'total_products': total_products,
                'revenue': str(revenue),
                'gst_collection': str(gst_collection)
            },
            'sales_trend': sales_trend,
            'recent_activities': recent_activities,
            'top_products': top_products,
            'low_stock_alerts': low_stock_alerts,
            'pending_approvals': pending_approvals
        }

        return success_response(data=data, message="Sub-Admin Dashboard data fetched successfully.")
import json
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from common.responses import success_response, error_response
from apps.branches.models import Branch
from apps.inventory.models import BranchStock
from apps.audit.models import AuditLog
from apps.accounts.models import User
from apps.products.models import Product
from apps.billing.models import Invoice, InvoiceItem, ExchangeRequest, Offer

from .models import Expense
from .serializers import ExpenseSerializer
from .services.report_generator import ReportGenerator
from .services.exporters import ReportExporter

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by('-date')
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'SUB_ADMIN':
            qs = qs.filter(branch_id=self.request.user.branch_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        branch = None

        if user.role == 'ADMIN' and 'branch' in self.request.data:
            from apps.branches.models import Branch
            try:
                branch = Branch.objects.get(id=self.request.data['branch'])
            except Branch.DoesNotExist:
                raise serializers.ValidationError({"branch": "Invalid branch ID provided."})

        if not branch:
            branch = user.branch

        if not branch:
            raise serializers.ValidationError({"branch": "You must be assigned to a branch to record expenses."})
            
        serializer.save(recorded_by=user, branch=branch)

class ExportReportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # Ignore DRF's format query parameter so ?format=pdf doesn't trigger 404
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), JSONRenderer.media_type)

    def get(self, request):
        report_type = request.query_params.get('type')
        format_type = request.query_params.get('format', 'excel').lower()
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not report_type:
            return error_response(message="Missing report 'type' parameter", status=400)

        # Date parsing
        end_date = timezone.now()
        if end_date_str:
            from django.utils.dateparse import parse_date
            parsed_end = parse_date(end_date_str)
            if parsed_end:
                end_date = timezone.make_aware(timezone.datetime.combine(parsed_end, timezone.datetime.max.time()))

        start_date = end_date - timedelta(days=30)
        if start_date_str:
            from django.utils.dateparse import parse_date
            parsed_start = parse_date(start_date_str)
            if parsed_start:
                start_date = timezone.make_aware(timezone.datetime.combine(parsed_start, timezone.datetime.min.time()))

        branch_id = request.user.branch_id if request.user.role == 'SUB_ADMIN' else None
        
        # Generator
        data = []
        headers = []
        title = f"{report_type.replace('_', ' ').title()} Report"

        if report_type == 'daily_sales':
            raw = ReportGenerator.get_daily_sales(start_date, end_date, branch_id)
            headers = ['Date', 'Total Revenue', 'Total Invoices', 'CGST', 'SGST', 'IGST']
            data = [[r['date'].strftime('%Y-%m-%d'), r['total_revenue'], r['total_invoices'], r['total_cgst'], r['total_sgst'], r['total_igst']] for r in raw]

        elif report_type == 'monthly_sales':
            raw = ReportGenerator.get_monthly_sales(start_date, end_date, branch_id)
            headers = ['Month', 'Total Revenue', 'Total Invoices']
            data = [[r['month'].strftime('%Y-%m'), r['total_revenue'], r['total_invoices']] for r in raw]

        elif report_type == 'stock_report':
            raw = ReportGenerator.get_stock_report(branch_id)
            headers = ['Branch', 'Product Name', 'Product Code', 'Quantity', 'Purchase Price', 'Total Valuation']
            data = [[r['branch'], r['product_name'], r['product_code'], r['quantity'], r['purchase_price'], r['total_valuation']] for r in raw]

        elif report_type == 'expense_report':
            raw = ReportGenerator.get_expense_report(start_date, end_date, branch_id)
            headers = ['Date', 'Branch', 'Category', 'Amount', 'Recorded By', 'Notes']
            data = [[r['date'], r['branch__name'], r['category'], r['amount'], r['recorded_by__first_name'], r['notes']] for r in raw]

        elif report_type == 'profit_summary':
            raw = ReportGenerator.get_profit_summary(start_date, end_date, branch_id)
            headers = ['Metric', 'Amount']
            data = [
                ['Total Revenue', raw['total_revenue']],
                ['Cost of Goods Sold', raw['cost_of_goods_sold']],
                ['Gross Profit', raw['gross_profit']],
                ['Total Expenses', raw['total_expenses']],
                ['Net Profit', raw['net_profit']]
            ]

        elif report_type == 'gst_report':
            raw = ReportGenerator.get_gst_report(start_date, end_date, branch_id)
            headers = ['Invoice Number', 'Date', 'Grand Total', 'CGST', 'SGST', 'IGST']
            data = [[r['invoice_number'], r['created_at'].strftime('%Y-%m-%d'), r['grand_total'], r['total_cgst'], r['total_sgst'], r['total_igst']] for r in raw]

        elif report_type == 'returns_report':
            raw = ReportGenerator.get_returns_report(start_date, end_date, branch_id)
            headers = ['Request ID', 'Invoice Number', 'Status', 'Date', 'Approved By']
            data = [[r['id'], r['invoice__invoice_number'], r['status'], r['created_at'].strftime('%Y-%m-%d'), r['approved_by__first_name']] for r in raw]

        elif report_type == 'cashier_sales':
            raw = ReportGenerator.get_cashier_sales(start_date, end_date, branch_id)
            headers = ['Cashier Name', 'Total Revenue', 'Total Invoices']
            data = [[f"{r['created_by__first_name']} {r['created_by__last_name']}", r['total_revenue'], r['total_invoices']] for r in raw]
            
        else:
            return error_response(message="Invalid report type", status=400)

        # Export
        if format_type == 'pdf':
            file_data = ReportExporter.generate_pdf(data, headers, title)
            content_type = 'application/pdf'
            ext = 'pdf'
        else:
            file_data = ReportExporter.generate_excel(data, headers, title)
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ext = 'xlsx'

        response = HttpResponse(file_data, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d")}.{ext}"'
        return response

class TopProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.billing.models import InvoiceItem
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        limit = int(request.query_params.get('limit', 20))
        branch_id = request.user.branch_id if request.user.role == 'SUB_ADMIN' else request.query_params.get('branch_id')
        
        qs = InvoiceItem.objects.all()
        if branch_id:
            qs = qs.filter(invoice__branch_id=branch_id)
            
        top_items = qs.values('product_name_snapshot', 'product_id').annotate(
            total_sold=Count('id')
        ).order_by('-total_sold')[:limit]
        
        top_products = []
        for item in top_items:
            top_products.append({
                'product_id': item['product_id'],
                'product_name': item['product_name_snapshot'],
                'total_sold': item['total_sold']
            })
            
        from rest_framework.response import Response
        return Response({
            'success': True,
            'top_products': top_products
        })


class GSTReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        end_date = timezone.now()
        if end_date_str:
            from django.utils.dateparse import parse_date
            parsed_end = parse_date(end_date_str)
            if parsed_end:
                end_date = timezone.make_aware(timezone.datetime.combine(parsed_end, timezone.datetime.max.time()))

        start_date = end_date - timedelta(days=30)
        if start_date_str:
            from django.utils.dateparse import parse_date
            parsed_start = parse_date(start_date_str)
            if parsed_start:
                start_date = timezone.make_aware(timezone.datetime.combine(parsed_start, timezone.datetime.min.time()))

        invoices = Invoice.objects.filter(created_at__range=[start_date, end_date])
        
        branch_id = request.user.branch_id if request.user.role == 'SUB_ADMIN' else request.query_params.get('branch_id')
        if branch_id:
            invoices = invoices.filter(branch_id=branch_id)

        totals = invoices.aggregate(
            total_cgst=Sum('total_cgst'),
            total_sgst=Sum('total_sgst'),
            total_igst=Sum('total_igst')
        )
        
        total_cgst = totals['total_cgst'] or Decimal('0.00')
        total_sgst = totals['total_sgst'] or Decimal('0.00')
        total_igst = totals['total_igst'] or Decimal('0.00')
        total_gst = total_cgst + total_sgst + total_igst

        daily_gst = invoices.annotate(day=TruncDay('created_at')).values('day').annotate(
            cgst=Sum('total_cgst'),
            sgst=Sum('total_sgst'),
            igst=Sum('total_igst')
        ).order_by('-day')
        
        breakdown = []
        for day_data in daily_gst:
            breakdown.append({
                'date': day_data['day'].strftime('%Y-%m-%d'),
                'cgst': str(day_data['cgst'] or '0.00'),
                'sgst': str(day_data['sgst'] or '0.00'),
                'igst': str(day_data['igst'] or '0.00'),
                'total_daily_gst': str((day_data['cgst'] or Decimal('0.00')) + (day_data['sgst'] or Decimal('0.00')) + (day_data['igst'] or Decimal('0.00')))
            })

        data = {
            'summary': {
                'total_cgst': str(total_cgst),
                'total_sgst': str(total_sgst),
                'total_igst': str(total_igst),
                'total_gst_collected': str(total_gst)
            },
            'daily_breakdown': breakdown
        }

        return success_response(data=data, message='GST report fetched successfully.')


class EmployeeDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Determine today's date boundaries
        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 1. Branch Info
        branch_name = user.branch.name if user.branch else None
        
        # 2. Shift Status
        from apps.billing.models import Shift, ExchangeRequest
        active_shift = Shift.objects.filter(cashier=user, status='OPEN').first()
        shift_status = 'OPEN' if active_shift else 'CLOSED'
        shift_opened_at = active_shift.opened_at if active_shift else None
        
        # 3. Summary Cards (Today)
        todays_invoices = Invoice.objects.filter(created_by=user, created_at__gte=start_of_today)
        invoices_count = todays_invoices.count()
        revenue_today = todays_invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        returns_count = ExchangeRequest.objects.filter(
            requested_by=user, 
            request_type='RETURN', 
            created_at__gte=start_of_today
        ).count()
        
        # 4. Recent Transactions
        recent_invoices = Invoice.objects.filter(created_by=user).order_by('-created_at')[:5]
        recent_transactions = []
        for inv in recent_invoices:
            recent_transactions.append({
                'id': str(inv.id),
                'invoice_number': inv.invoice_number,
                'amount': str(inv.grand_total),
                'payment_mode': inv.payment_mode,
                'time': inv.created_at.strftime('%I:%M %p')
            })
            
        data = {
            'branch_name': branch_name,
            'shift_status': shift_status,
            'shift_opened_at': shift_opened_at,
            'summary_cards': {
                'invoices_today': invoices_count,
                'revenue_today': str(revenue_today),
                'returns_today': returns_count
            },
            'recent_transactions': recent_transactions
        }
        
        return success_response(data=data, message="Employee Dashboard fetched successfully.")

