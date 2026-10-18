import io
import math
import secrets
import time
from datetime import timedelta

import pyotp
import qrcode
import qrcode.image.svg
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .audit import record_operation_audit
from .authentication import ExpiryTokenAuthentication
from .models import AuthChallenge, LoginSession, UserTwoFactor
from .security import decrypt_value, encrypt_value
from .settings_views import get_system_setting
from .views import ensure_development_admin, serialize_user


class LoginThrottle(AnonRateThrottle):
    rate = "30/minute"


def browser_key(request):
    if not request.session.get("login_browser"):
        request.session["login_browser"] = secrets.token_urlsafe(24)
    return request.session["login_browser"]


def new_challenge(request, kind, payload, seconds=120):
    AuthChallenge.objects.filter(expires_at__lte=timezone.now()).delete()
    challenge_id = secrets.token_urlsafe(32)
    AuthChallenge.objects.create(
        id=challenge_id, kind=kind,
        payload={**payload, "browser": browser_key(request)},
        expires_at=timezone.now() + timedelta(seconds=seconds),
    )
    return challenge_id


def find_challenge(request, kind, identifier):
    challenge = AuthChallenge.objects.select_for_update().filter(
        pk=str(identifier or ""), kind=kind, expires_at__gt=timezone.now(), attempts__lt=5,
    ).first()
    if not challenge or not constant_time_compare(challenge.payload.get("browser", ""), browser_key(request)):
        return None
    return challenge


def failed_attempt(challenge):
    challenge.attempts += 1
    if challenge.attempts >= 5:
        challenge.delete()
    else:
        challenge.save(update_fields=["attempts"])


def credential_stamp(user):
    return salted_hmac("filehub-login", user.password).hexdigest()


def consume_code(record, code):
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    generator = pyotp.TOTP(decrypt_value(record.encrypted_secret))
    now_step = int(time.time() // 30)
    for step in (now_step - 1, now_step, now_step + 1):
        if step > record.last_step and generator.verify(code, for_time=step * 30):
            changed = UserTwoFactor.objects.filter(pk=record.pk, last_step__lt=step).update(last_step=step)
            return bool(changed)
    return False


def issue_token(user):
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    expiry = token.created + timedelta(minutes=get_system_setting().login_expiry_minutes)
    LoginSession.objects.create(token=token, expires_at=expiry)
    update_last_login(None, user)
    user.refresh_from_db(fields=["last_login"])
    return {"token": token.key, "expires_at": expiry.timestamp(), "user": serialize_user(user)}


def setup_payload(user, secret, challenge):
    uri = pyotp.TOTP(secret).provisioning_uri(user.username, issuer_name="FileHub")
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    import base64
    return {
        "twoFactorSetupRequired": True,
        "challenge": challenge,
        "account": user.username,
        "expiresIn": 300,
        "secret": secret,
        "otpauth_url": uri,
        "qr_data_url": "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode(),
    }


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def slider_challenge(request):
    target = secrets.randbelow(181) + 80
    challenge_id = new_challenge(request, "slider", {"target": target, "started": time.time()})
    return Response({"challengeId": challenge_id, "targetX": target, "trackWidth": 320, "tolerance": 8, "expiresIn": 120})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def slider_verify(request):
    with transaction.atomic():
        challenge = find_challenge(request, "slider", request.data.get("challengeId"))
        try:
            offset, elapsed = float(request.data.get("offsetX")), int(request.data.get("elapsedMs", 0))
        except (TypeError, ValueError, OverflowError):
            return Response({"detail": "滑块参数无效"}, status=400)
        if not challenge:
            return Response({"detail": "滑块已过期，请重试"}, status=400)
        if not math.isfinite(offset) or elapsed < 500 or time.time() - challenge.payload["started"] < 0.5 or abs(offset - challenge.payload["target"]) > 8:
            failed_attempt(challenge)
            return Response({"detail": "滑块验证失败，请重试"}, status=400)
        challenge.delete()
        token = new_challenge(request, "slider_token", {})
    return Response({"sliderToken": token})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    with transaction.atomic():
        slider = find_challenge(request, "slider_token", request.data.get("sliderToken"))
        if not slider:
            return Response({"detail": "请先完成滑块验证"}, status=400)
        slider.delete()
        ensure_development_admin()
        username = str(request.data.get("username", request.data.get("account", ""))).strip()
        user = authenticate(request, username=username, password=str(request.data.get("password", "")))
        if not user:
            record_operation_audit(request, "认证", "登录失败", username, "账号或密码错误")
            return Response({"detail": "账号或密码错误"}, status=400)
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        record = UserTwoFactor.objects.filter(user=user).first()
        if record and record.required:
            secret = pyotp.random_base32()
            challenge = new_challenge(request, "login_2fa_setup", {
                "user_id": user.pk,
                "secret": encrypt_value(secret),
                "credentials": credential_stamp(user),
            }, seconds=300)
            return Response(setup_payload(user, secret, challenge))
        if record and record.enabled:
            challenge = new_challenge(request, "login_2fa", {
                "user_id": user.pk, "credentials": credential_stamp(user),
                "secret_stamp": salted_hmac("filehub-totp", record.encrypted_secret).hexdigest(),
            }, seconds=300)
            return Response({"twoFactorRequired": True, "challenge": challenge})
        record_operation_audit(request, "认证", "登录", username, "登录成功", user=user)
        return Response(issue_token(user))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def verify_login(request):
    with transaction.atomic():
        challenge = find_challenge(request, "login_2fa", request.data.get("challenge"))
        if not challenge:
            return Response({"detail": "验证已过期，请重新登录", "restart_login": True}, status=400)
        user = get_user_model().objects.select_for_update().filter(pk=challenge.payload["user_id"], is_active=True).first()
        record = UserTwoFactor.objects.select_for_update().filter(user=user, enabled=True).first() if user else None
        if not record or not constant_time_compare(challenge.payload["credentials"], credential_stamp(user)) or not constant_time_compare(challenge.payload["secret_stamp"], salted_hmac("filehub-totp", record.encrypted_secret).hexdigest()):
            challenge.delete()
            return Response({"detail": "账号认证状态已变更，请重新登录", "restart_login": True}, status=400)
        if consume_code(record, str(request.data.get("code", "")).strip()):
            challenge.delete()
            record_operation_audit(request, "认证", "双因素登录", user.username, "动态验证码验证成功", user=user)
            return Response(issue_token(user))
        failed_attempt(challenge)
        record_operation_audit(request, "认证", "双因素登录失败", user.username, "动态验证码验证失败", user=user)
        return Response({"detail": "动态验证码无效或已使用", "restart_login": challenge.attempts >= 5}, status=400)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def verify_setup(request):
    with transaction.atomic():
        challenge = find_challenge(request, "login_2fa_setup", request.data.get("challenge"))
        if not challenge:
            return Response({"detail": "绑定已过期，请重新登录", "restart_login": True}, status=400)
        user = get_user_model().objects.select_for_update().filter(pk=challenge.payload["user_id"], is_active=True).first()
        record = UserTwoFactor.objects.select_for_update().filter(user=user).first() if user else None
        if not user or not record or not record.required or not constant_time_compare(challenge.payload["credentials"], credential_stamp(user)):
            challenge.delete()
            return Response({"detail": "双因素认证状态已变更，请重新登录", "restart_login": True}, status=400)
        secret = decrypt_value(challenge.payload["secret"])
        code = str(request.data.get("code", "")).strip()
        if len(code) != 6 or not code.isascii() or not code.isdigit() or not pyotp.TOTP(secret).verify(code, valid_window=1):
            failed_attempt(challenge)
            return Response({"detail": "验证码无效"}, status=400)
        record.encrypted_secret = challenge.payload["secret"]
        record.enabled = True
        record.required = False
        record.bound_at = timezone.now()
        record.last_step = -1
        record.save(update_fields=["encrypted_secret", "enabled", "required", "bound_at", "last_step"])
        challenge.delete()
        record_operation_audit(request, "双因素认证", "绑定", user.username, "完成首次 TOTP 绑定", user=user)
        return Response(issue_token(user))


def manage_two_factor(request, user_id, action):
    if not request.user.is_superuser:
        return Response({"detail": "仅超级管理员可以执行此操作"}, status=403)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().filter(pk=user_id).first()
        if not user:
            return Response({"detail": "用户不存在"}, status=404)
        if user.username == "admin" or user.pk == request.user.pk:
            return Response({"detail": "内置管理员或当前登录用户不允许在用户列表中操作 2FA"}, status=400)
        record, _ = UserTwoFactor.objects.get_or_create(user=user)
        if action == "enable":
            record.encrypted_secret = ""
            record.enabled = False
            record.required = True
            record.bound_at = None
            record.last_step = -1
            audit_action = "开启"
        elif action == "disable":
            record.encrypted_secret = ""
            record.enabled = False
            record.required = False
            record.bound_at = None
            record.last_step = -1
            audit_action = "关闭"
        else:
            record.encrypted_secret = ""
            record.enabled = False
            record.required = True
            record.bound_at = None
            record.last_step = -1
            audit_action = "重置"
        record.save(update_fields=["encrypted_secret", "enabled", "required", "bound_at", "last_step"])
        AuthChallenge.objects.filter(kind__in=["login_2fa", "login_2fa_setup"], payload__user_id=user.pk).delete()
        record_operation_audit(request, "双因素认证", f"管理员{audit_action}", user.username, f"管理员{audit_action}用户双因素认证", user=request.user)
    return Response(serialize_user(user))


@api_view(["POST"])
@authentication_classes([ExpiryTokenAuthentication])
@permission_classes([IsAuthenticated])
def enable_two_factor(request, user_id):
    return manage_two_factor(request, user_id, "enable")


@api_view(["POST"])
@authentication_classes([ExpiryTokenAuthentication])
@permission_classes([IsAuthenticated])
def disable_two_factor(request, user_id):
    return manage_two_factor(request, user_id, "disable")


@api_view(["POST"])
@authentication_classes([ExpiryTokenAuthentication])
@permission_classes([IsAuthenticated])
def reset_two_factor(request, user_id):
    return manage_two_factor(request, user_id, "reset")
