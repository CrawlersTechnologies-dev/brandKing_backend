from django.db import models
from django.conf import settings
from apps.branches.models import Branch

class Expense(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=100, help_text="e.g., Petty Cash, Utilities, Rent")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')

    def __str__(self):
        return f"{self.category} - {self.amount}"
