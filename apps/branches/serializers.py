from rest_framework import serializers
from .models import Branch, Counter

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class CounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Counter
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


    def to_internal_value(self, data):
        if hasattr(data, '_mutable'):
            data = data.copy()
        branch_val = data.get('branch')
        if branch_val and isinstance(branch_val, str):
            import uuid
            try:
                uuid.UUID(branch_val)
            except ValueError:
                from apps.branches.models import Branch
                try:
                    b = Branch.objects.get(name__iexact=branch_val)
                    data['branch'] = b.id
                except Branch.DoesNotExist:
                    raise serializers.ValidationError({'branch': f"Branch '{branch_val}' does not exist."})
        return super().to_internal_value(data)

    def to_internal_value(self, data):
        if hasattr(data, '_mutable'):
            data = data.copy()
        branch_val = data.get('branch')
        if branch_val and isinstance(branch_val, str) and not branch_val.isdigit():
            import uuid
            try:
                uuid.UUID(branch_val)
            except ValueError:
                from .models import Branch
                try:
                    b = Branch.objects.get(name__iexact=branch_val)
                    data['branch'] = b.id
                except Branch.DoesNotExist:
                    raise serializers.ValidationError({'branch': f"Branch '{branch_val}' does not exist."})
        return super().to_internal_value(data)
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.branch:
            representation['branch'] = instance.branch.name
        return representation
