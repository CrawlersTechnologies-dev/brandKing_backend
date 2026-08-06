from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserDocument
from apps.branches.models import Branch
from apps.audit.models import AuditLog
from common.constants import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_SUB_ADMIN

class UserDocumentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch1 = Branch.objects.create(name='Branch 1', code='B1')
        self.branch2 = Branch.objects.create(name='Branch 2', code='B2')
        
        self.admin = User.objects.create_superuser(
            email='admin@brandking.com', password='password123'
        )
        self.subadmin = User.objects.create_user(
            email='subadmin@brandking.com', password='password123', role=ROLE_SUB_ADMIN, branch=self.branch1
        )
        self.employee1 = User.objects.create_user(
            email='emp1@brandking.com', password='password123', role=ROLE_EMPLOYEE, branch=self.branch1
        )
        self.employee2 = User.objects.create_user(
            email='emp2@brandking.com', password='password123', role=ROLE_EMPLOYEE, branch=self.branch2
        )

        self.valid_pdf = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        self.valid_jpg = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        self.invalid_file = SimpleUploadedFile("test.exe", b"malicious", content_type="application/x-msdownload")
        self.large_file = SimpleUploadedFile("large.jpg", b"0" * (6 * 1024 * 1024), content_type="image/jpeg")

    def test_employee_creation_without_documents(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/employees/', {
            'email': 'nodoc@brandking.com',
            'password': 'password123',
            'branch': self.branch1.id,
            'first_name': 'NoDoc'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='nodoc@brandking.com')
        self.assertEqual(user.documents.count(), 0)

    def test_employee_creation_with_documents_legacy(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/employees/', {
            'email': 'withdoc@brandking.com',
            'password': 'password123',
            'branch': self.branch1.id,
            'profile_photo': self.valid_jpg,
            'aadhaar': self.valid_pdf
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='withdoc@brandking.com')
        self.assertEqual(user.documents.count(), 2)

    def test_invalid_file_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/employees/{self.employee1.id}/documents/', {
            'document_type': 'PAN',
            'file': self.invalid_file
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_file_size_validation(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/employees/{self.employee1.id}/documents/', {
            'document_type': 'PROFILE_PHOTO',
            'file': self.large_file
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_standalone_document_upload(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/employees/{self.employee1.id}/documents/', {
            'document_type': 'AADHAAR',
            'file': self.valid_pdf
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserDocument.objects.filter(user=self.employee1, document_type='AADHAAR').count(), 1)
        
        # Test Audit log
        self.assertTrue(AuditLog.objects.filter(action='CREATED', object_type='UserDocument').exists())

    def test_document_verification(self):
        doc = UserDocument.objects.create(user=self.employee1, document_type='PAN', file=self.valid_jpg)
        
        # Admin verifies
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f'/api/employees/{self.employee1.id}/documents/{doc.id}/', {
            'is_verified': True,
            'remarks': 'Looks good'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertTrue(doc.is_verified)
        self.assertEqual(doc.verified_by, self.admin)
        
        # Test Audit Log for verification
        self.assertTrue(AuditLog.objects.filter(action='VERIFIED').exists())

    def test_subadmin_cannot_verify(self):
        doc = UserDocument.objects.create(user=self.employee1, document_type='PAN', file=self.valid_jpg)
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.patch(f'/api/employees/{self.employee1.id}/documents/{doc.id}/', {
            'is_verified': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_branch_access_restriction(self):
        # Subadmin in branch 1 tries to access employee in branch 2
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.get(f'/api/employees/{self.employee2.id}/documents/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_deletion(self):
        doc = UserDocument.objects.create(user=self.employee1, document_type='PAN', file=self.valid_jpg)
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/employees/{self.employee1.id}/documents/{doc.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserDocument.objects.filter(id=doc.id).count(), 0)
        self.assertTrue(AuditLog.objects.filter(action='DELETED', object_type='UserDocument').exists())
