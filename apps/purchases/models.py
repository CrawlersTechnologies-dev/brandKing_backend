import uuid
from django.db import models
from django.conf import settings
from apps.branches.models import Branch

class InventoryInward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.RESTRICT)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    total_quantity = models.IntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_inwards'

    def __str__(self):
        return f"Inward {self.id} at {self.branch.name}"
