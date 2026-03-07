import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.sessions import SessionMiddlewareStack
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sar_portal.settings')

django_asgi_app = get_asgi_application()

from sar_portal import consumers

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': SessionMiddlewareStack(
        URLRouter([
            re_path(r'^ws/chat/(?P<room_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
        ])
    ),
})
