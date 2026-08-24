from rest_framework import serializers
from .models import Expense

class ExpenseSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.first_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['recorded_by', 'created_at']
