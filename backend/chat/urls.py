"""
URL patterns for the chat app.
Maps all Flask routes to Django views.
"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/chat", views.api_chat, name="api_chat"),
    path("api/chat/", views.api_chat, name="api_chat_slash"),
    path("get", views.legacy_get, name="legacy_get"),
    path("get/", views.legacy_get, name="legacy_get_slash"),
    path("api/health", views.health, name="health"),
    path("api/health/", views.health, name="health_slash"),
    path("api/debug/knowledge", views.debug_knowledge, name="debug_knowledge"),
    path("api/debug/knowledge/", views.debug_knowledge, name="debug_knowledge_slash"),
]
