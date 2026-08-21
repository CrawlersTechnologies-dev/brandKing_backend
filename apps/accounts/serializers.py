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

    def to_internal_value(self, data):
        if hasattr(data, '_mutable'):
            data = data.copy()
        branch_val = data.get('branch')
        if branch_val and isinstance(branch_val, str) and not branch_val.isdigit():
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
    branch_details = BranchSerializer(source='branch', read_only=True)
    documents = UserDocumentSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'address', 'role', 'branch', 'branch_name', 'branch_details', 'is_active', 'is_approved', 'password', 'documents']
        extra_kwargs = {
            'password': {'write_only': True},
            'is_active': {'default': True},
            'is_approved': {'read_only': True},
        }

    def to_internal_value(self, data):
        # Workaround for DRF multipart/form-data boolean parsing
        mutable_data = data.copy() if hasattr(data, 'copy') else data
        if 'is_active' not in mutable_data:
            mutable_data['is_active'] = True
            
        if 'branch' in mutable_data:
            branch_val = mutable_data['branch']
            if branch_val:
                import uuid
                try:
                    uuid.UUID(str(branch_val))
                except ValueError:
                    from apps.branches.models import Branch
                    branch = Branch.objects.filter(name__iexact=branch_val).first() or Branch.objects.filter(code__iexact=branch_val).first()
                    if branch:
                        mutable_data['branch'] = branch.id
                    else:
                        raise serializers.ValidationError({"branch": f"No branch found matching '{branch_val}'"})
                        
        return super().to_internal_value(mutable_data)

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

class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=6)

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        if not self.user.is_approved:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed('Your account is pending approval by an administrator.')
            
        # Add custom claims to the response payload
        data['user'] = {
            'id': str(self.user.id),
            'email': self.user.email,
            'first_name': self.user.first_name,
            'role': self.user.role,
            'branch_id': str(self.user.branch.id) if self.user.branch else None
        }
        return data
