"""
Django ORM models for Braelo: User, ChatHistory, KnowledgeBase, AdPackage, Business, ImpressionsLog, Lead.
Ported from SQLAlchemy models (database/models.py).
"""
from django.db import models
from django.utils import timezone


class User(models.Model):
    """Chat user identified by an external ID (phone, session, etc.)."""
    external_id = models.CharField(max_length=128, unique=True, db_index=True)
    language_preference = models.CharField(max_length=8, default="en")
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.external_id


class ChatHistory(models.Model):
    """Stores every user ↔ assistant message."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    role = models.CharField(max_length=16)  # user | assistant
    content = models.TextField()
    intent = models.CharField(max_length=64, null=True, blank=True)
    entities_json = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "chat_history"

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class KnowledgeBase(models.Model):
    """Q&A knowledge base loaded from DOCX files, with optional OpenAI embeddings."""
    state = models.CharField(max_length=64, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField()
    embedding_json = models.TextField(null=True, blank=True)  # JSON array of floats
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "knowledge_base"

    def __str__(self):
        return self.question[:80]


class AdPackage(models.Model):
    """Ad packages that businesses can subscribe to for priority placement."""
    name = models.CharField(max_length=64)
    priority = models.IntegerField(default=0)  # higher = shown first
    max_impressions = models.IntegerField(default=1000)

    class Meta:
        db_table = "ad_packages"

    def __str__(self):
        return self.name


class Business(models.Model):
    """Local businesses that can be recommended to users."""
    name = models.CharField(max_length=256)
    category = models.CharField(max_length=128, null=True, blank=True)
    subcategory = models.CharField(max_length=128, null=True, blank=True)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=128, null=True, blank=True)
    languages = models.CharField(max_length=256, null=True, blank=True)  # comma-separated: en,es,pt
    contact_info = models.TextField(null=True, blank=True)
    ad_package = models.ForeignKey(AdPackage, on_delete=models.SET_NULL, null=True, blank=True)
    impression_cap = models.IntegerField(default=1000)
    impressions_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "businesses"

    def __str__(self):
        return self.name


class ImpressionsLog(models.Model):
    """Log of every time a business is shown to a user."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True)
    session_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "impressions_log"


class Lead(models.Model):
    """Tracks user actions (clicks) on businesses."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True)
    action_type = models.CharField(max_length=32, default="click")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "leads"
