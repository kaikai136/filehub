from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import LoginSession, SystemSetting


def token_expired(token):
    setting = SystemSetting.objects.filter(pk=1).first()
    minutes = setting.login_expiry_minutes if setting else 480
    expiry = token.created + timedelta(minutes=minutes)
    session = LoginSession.objects.filter(token=token).first()
    if session:
        expiry = min(expiry, session.expires_at)
    return timezone.now() >= expiry


class ExpiryTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token_expired(token):
            token.delete()
            raise AuthenticationFailed("登录已过期，请重新登录")
        return user, token
