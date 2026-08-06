from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.branches.models import Branch
from apps.accounts.models import User
from common.constants import ROLE_ADMIN, ROLE_EMPLOYEE

class BranchAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            email='admin@brandking.com',
            password='password123'
        )
        self.employee_user = User.objects.create_user(
            email='employee@brandking.com',
            password='password123',
            role=ROLE_EMPLOYEE
        )
        self.branch1 = Branch.objects.create(name='Main Branch', code='MAIN')

    def test_branch_creation_by_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/branches/', {
            'name': 'Second Branch',
            'code': 'SEC',
            'address': '123 Street'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Branch.objects.count(), 2)

    def test_branch_creation_by_employee_forbidden(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/branches/', {
            'name': 'Third Branch',
            'code': 'THIRD',
            'address': '123 Street'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Branch.objects.count(), 1)

    def test_list_branches_by_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/branches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data['data'])
            
