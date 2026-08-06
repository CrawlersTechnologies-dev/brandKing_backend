from rest_framework import serializers
from .models import User, UserDocument
from apps.branches.serializers import BranchSerializer

class UserDocumentSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UserDocument
        fields = ['id', 'document_type', 'file', 'uploaded_at', 'is_verified', 'verified_by', 'verified_by_name', 'verified_at', 'remarks']
        read_only_fields = ['is_verified', 'verified_by', 'verified_by_name', 'verified_at', 'remarks']

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return f"{obj.verified_by.first_name} {obj.verified_by.last_name}".strip() or obj.verified_by.email
        return None

class DocumentVerifySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDocument
        fields = ['is_verified', 'remarks']

class UserSerializer(serializers.ModelSerializer):
    branch_details = BranchSerializer(source='branch', read_only=True)
    documents = UserDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'address', 'role', 'branch', 'branch_details', 'is_active', 'password', 'documents']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
