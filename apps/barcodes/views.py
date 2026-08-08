from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from apps.inventory.models import SerializedItem
from .services import LabelPrinterService

class LabelPrintView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        item_ids = request.query_params.get('items', '')
        include_sp = request.query_params.get('include_selling_price', 'false').lower() == 'true'
        
        if not item_ids:
            from common.responses import error_response
            return error_response("items parameter is required (comma-separated UUIDs).", status=400)
            
        uuid_list = [i.strip() for i in item_ids.split(',') if i.strip()]
        
        items = SerializedItem.objects.filter(id__in=uuid_list).select_related('product')
        if not items:
            from common.responses import error_response
            return error_response("No valid items found.", status=404)
            
        pdf_buffer = LabelPrinterService.generate_labels_pdf(items, include_selling_price=include_sp)
        
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="labels.pdf"'
        return response
