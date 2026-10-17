from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token


@database_sync_to_async
def user_from_token(token_key):
    try:
        token = Token.objects.select_related("user").get(key=token_key)
    except Token.DoesNotExist:
        return None
    user = token.user
    return user if user.is_active else None


class TokenQueryAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        token = query.get("token", [""])[0]
        scope["user"] = await user_from_token(token) if token else None
        return await self.app(scope, receive, send)
