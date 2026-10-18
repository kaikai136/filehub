from datetime import timedelta
from unittest.mock import patch

import pyotp
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APIClient

from .models import AuthChallenge, LoginSession, SystemSetting, UserTwoFactor
from .security import decrypt_value, encrypt_value
from .ws_auth import user_from_token


class LoginSecurityTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_superuser('secure-admin', password='password123')
        self.setting = SystemSetting.objects.create(pk=1)

    def slider(self):
        response = self.client.get('/api/auth/slider-challenge/')
        self.assertEqual(response.status_code, 200)
        data = response.data
        challenge = AuthChallenge.objects.get(pk=data['challengeId'])
        challenge.payload['started'] -= 1
        challenge.save()
        response = self.client.post('/api/auth/slider-verify/', {'challengeId': data['challengeId'], 'offsetX': data['targetX'], 'elapsedMs': 700})
        self.assertEqual(response.status_code, 200)
        return response.data['sliderToken']

    def login(self):
        return self.client.post('/api/auth/login/', {'username': self.user.username, 'password': 'password123', 'sliderToken': self.slider()})

    def authorize(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return token

    def test_slider_required_single_use_and_browser_bound(self):
        self.assertEqual(self.client.post('/api/auth/login/', {'username': self.user.username, 'password': 'password123'}).status_code, 400)
        slider = self.slider()
        other = APIClient()
        payload = {'username': self.user.username, 'password': 'password123', 'sliderToken': slider}
        self.assertEqual(other.post('/api/auth/login/', payload).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login/', payload).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/login/', payload).status_code, 400)

    def test_success_has_fixed_deadline_and_me_does_not_renew(self):
        result = self.login()
        self.assertEqual(result.status_code, 200)
        token = Token.objects.get(key=result.data['token'])
        session = LoginSession.objects.get(token=token)
        self.assertAlmostEqual((session.expires_at - token.created).total_seconds(), 480 * 60)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        token.refresh_from_db()
        self.assertEqual(session.expires_at, LoginSession.objects.get(token=token).expires_at)
        self.assertIsNotNone(self.login().data.get('token'))
        self.assertFalse(Token.objects.filter(key=token.key).exists())

    def test_expired_rest_and_websocket_rejected(self):
        token = self.authorize()
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=9))
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        token = Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=9))
        self.assertIsNone(async_to_sync(user_from_token)(token.key))

    def test_settings_validation_and_permissions(self):
        self.authorize()
        for value in [0, 43201, True, 1.5, '60']:
            self.assertEqual(self.client.patch('/api/settings/', {'settings': {'login_expiry_minutes': value}}, format='json').status_code, 400)
        for value in [1, 43200]:
            self.assertEqual(self.client.patch('/api/settings/', {'settings': {'login_expiry_minutes': value}}, format='json').status_code, 200)
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(self.client.patch('/api/settings/', {'settings': {'login_expiry_minutes': 60}}, format='json').status_code, 403)

    def test_totp_login_and_replay_protection(self):
        secret = pyotp.random_base32()
        UserTwoFactor.objects.create(user=self.user, enabled=True, encrypted_secret=encrypt_value(secret))
        result = self.login()
        self.assertTrue(result.data['twoFactorRequired'])
        self.assertNotIn('token', result.data)
        challenge = result.data['challenge']
        self.assertEqual(self.client.post('/api/auth/verify-two-factor/', {'challenge': challenge, 'code': 'bad'}).status_code, 400)
        code = pyotp.TOTP(secret).now()
        verified = self.client.post('/api/auth/verify-two-factor/', {'challenge': challenge, 'code': code})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.client.post('/api/auth/verify-two-factor/', {'challenge': challenge, 'code': code}).status_code, 400)
        next_challenge = self.login().data['challenge']
        self.assertEqual(self.client.post('/api/auth/verify-two-factor/', {'challenge': next_challenge, 'code': code}).status_code, 400)

    def test_totp_invalidated_after_password_change_or_reset(self):
        secret = pyotp.random_base32()
        UserTwoFactor.objects.create(user=self.user, enabled=True, encrypted_secret=encrypt_value(secret))
        challenge = self.login().data['challenge']
        self.user.set_password('changed-password')
        self.user.save()
        response = self.client.post('/api/auth/verify-two-factor/', {'challenge': challenge, 'code': pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data['restart_login'])

    def test_admin_controls_setup_and_user_cannot_self_manage(self):
        target = get_user_model().objects.create_user('managed-user', password='password123')
        admin_token = self.authorize()
        endpoint = '/api/users/' + str(target.pk) + '/two-factor/'
        self.assertEqual(self.client.post('/api/auth/two-factor/', {'action': 'setup'}).status_code, 404)
        self.assertEqual(self.client.post(endpoint + 'enable/').status_code, 200)
        record = UserTwoFactor.objects.get(user=target)
        self.assertTrue(record.required)
        self.assertFalse(record.enabled)

        target_client = APIClient()
        challenge = target_client.get('/api/auth/slider-challenge/').data
        slider = AuthChallenge.objects.get(pk=challenge['challengeId'])
        slider.payload['started'] -= 1
        slider.save()
        slider_token = target_client.post('/api/auth/slider-verify/', {'challengeId': challenge['challengeId'], 'offsetX': challenge['targetX'], 'elapsedMs': 700}).data['sliderToken']
        login = target_client.post('/api/auth/login/', {'username': target.username, 'password': 'password123', 'sliderToken': slider_token})
        self.assertTrue(login.data['twoFactorSetupRequired'])
        self.assertTrue(login.data['qr_data_url'].startswith('data:image/svg+xml;base64,'))
        code = pyotp.TOTP(login.data['secret']).now()
        completed = target_client.post('/api/auth/verify-two-factor-setup/', {'challenge': login.data['challenge'], 'code': code})
        self.assertEqual(completed.status_code, 200)
        record.refresh_from_db()
        self.assertTrue(record.enabled)
        self.assertFalse(record.required)

        target_client.credentials(HTTP_AUTHORIZATION='Token ' + completed.data['token'])
        self.assertEqual(target_client.post('/api/users/' + str(target.pk) + '/two-factor/enable/').status_code, 403)
        self.assertEqual(target_client.post('/api/auth/two-factor/', {'action': 'disable'}).status_code, 404)
        self.assertTrue(Token.objects.filter(key=completed.data['token']).exists())

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + admin_token.key)
        self.assertEqual(self.client.post(endpoint + 'disable/').status_code, 200)
        record.refresh_from_db()
        self.assertFalse(record.enabled)
        self.assertFalse(record.required)
        self.assertTrue(Token.objects.filter(key=completed.data['token']).exists())

    def test_admin_reset_requires_rebinding_without_revoking_sessions(self):
        target = get_user_model().objects.create_user('reset-user', password='password123')
        secret = pyotp.random_base32()
        UserTwoFactor.objects.create(user=target, enabled=True, encrypted_secret=encrypt_value(secret))
        target_token = Token.objects.create(user=target)
        self.authorize()
        endpoint = '/api/users/' + str(target.pk) + '/two-factor/reset/'
        response = self.client.post(endpoint)
        self.assertEqual(response.status_code, 200)
        record = UserTwoFactor.objects.get(user=target)
        self.assertFalse(record.enabled)
        self.assertTrue(record.required)
        self.assertTrue(Token.objects.filter(pk=target_token.pk).exists())

    def test_admin_reset_and_console_recovery(self):
        self.authorize()
        other = get_user_model().objects.create_user('other')
        UserTwoFactor.objects.create(user=other, enabled=True, encrypted_secret=encrypt_value(pyotp.random_base32()))
        other_token = Token.objects.create(user=other)
        endpoint = '/api/users/' + str(other.pk) + '/two-factor/reset/'
        self.assertEqual(self.client.post(endpoint).status_code, 200)
        self.assertTrue(Token.objects.filter(pk=other_token.pk).exists())
        self.assertEqual(self.client.post('/api/users/' + str(self.user.pk) + '/two-factor/reset/', {'password': 'password123'}).status_code, 400)
        UserTwoFactor.objects.create(user=self.user, enabled=True, encrypted_secret=encrypt_value(pyotp.random_base32()))
        call_command('reset_two_factor', self.user.username)
        record = UserTwoFactor.objects.get(user=self.user)
        self.assertTrue(record.required)
        self.assertFalse(record.enabled)
