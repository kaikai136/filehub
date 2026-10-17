from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import OperationAudit


User = get_user_model()


class UnlockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("lock-user", password="secret123")
        self.client.force_authenticate(self.user)

    def test_unlock_requires_current_password(self):
        response = self.client.post("/api/auth/unlock/", {"password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unlock_succeeds_without_replacing_session_and_records_audit(self):
        response = self.client.post("/api/auth/unlock/", {"password": "secret123"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(OperationAudit.objects.filter(operator=self.user, module="认证", action="解锁屏幕").exists())
