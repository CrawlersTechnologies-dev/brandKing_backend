import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.test import Client
from apps.accounts.models import User
c = Client()
res = c.post('/api/auth/login/', {'email': 'admin_test2@test.com', 'password': 'password'})
token = res.json()['access']
try:
    res2 = c.post('/api/categories/', {'name': 'TestCat4', 'code': 'TC4'}, HTTP_AUTHORIZATION=f'Bearer {token}')
    print("Status Code:", res2.status_code)
    print("Response JSON:", res2.json())
except Exception as e:
    import traceback
    traceback.print_exc()
