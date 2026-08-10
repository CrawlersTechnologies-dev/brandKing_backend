from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsGlobalAdmin
from common.responses import success_response
from .models import Branch, Counter
from .serializers import BranchSerializer, CounterSerializer

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all().order_by('-created_at')
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsGlobalAdmin]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict) and 'results' in response.data:
            return response # Already paginated and formatted by CustomPagination
        return success_response(data=response.data, message="Branches fetched successfully")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return success_response(data=response.data, message="Branch fetched successfully")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return success_response(data=response.data, message="Branch created successfully", status=201)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return success_response(data=response.data, message="Branch updated successfully")
        
    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return success_response(message="Branch deleted successfully", status=200)

class CounterViewSet(viewsets.ModelViewSet):
    queryset = Counter.objects.all().order_by('name')
    serializer_class = CounterSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsGlobalAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'ADMIN':
            return self.queryset
        if getattr(user, 'branch', None):
            return self.queryset.filter(branch=user.branch)
        return self.queryset.none()
        
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict) and 'results' in response.data:
            return response
        return success_response(data=response.data, message="Counters fetched successfully")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return success_response(data=response.data, message="Counter fetched successfully")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return success_response(data=response.data, message="Counter created successfully", status=201)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return success_response(data=response.data, message="Counter updated successfully")
        
    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return success_response(message="Counter deleted successfully", status=200)
