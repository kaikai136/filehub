from django.urls import re_path

from .consumers import CommandExecutionConsumer


websocket_urlpatterns = [
    re_path(r"^ws/command-executions/(?P<execution_id>[0-9]+)/$", CommandExecutionConsumer.as_asgi()),
]
