import uuid
import os
from django.db import models
from .validators import validate_file_extension, validate_file_size
from django.contrib.auth.models import AbstractUser, BaseUserManager
from common.constants import ROLE_CHOICES, ROLE_STORE_STAFF, ROLE_SUB_ADMIN, ROLE_ADMIN
from apps.branches.models import Branch

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', ROLE_ADMIN)

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None  # Remove username field
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STORE_STAFF)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    is_approved = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

def user_directory_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'user_documents/{instance.user.id}/{uuid.uuid4().hex}{ext}'

class UserDocument(models.Model):
    DOCUMENT_TYPES = [
        ('PROFILE_PHOTO', 'Profile Photo'),
        ('AADHAAR', 'Aadhaar'),
        ('PAN', 'PAN'),
        ('ADDRESS_PROOF', 'Address Proof'),
        ('OTHER', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to=user_directory_path, validators=[validate_file_extension, validate_file_size])
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Verification fields
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'user_documents'

    def __str__(self):
        return f"{self.user.email} - {self.get_document_type_display()}"

class PasswordResetOTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_otps'

    def __str__(self):
        return f"{self.user.email} - {self.otp}"
