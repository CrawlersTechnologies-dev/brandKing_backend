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
