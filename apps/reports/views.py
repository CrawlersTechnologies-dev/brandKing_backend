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
        if not branch:
            return error_response(message="User has no branch assigned", status=400)
            
        invoices = Invoice.objects.filter(branch=branch)
        
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
