"""
MongoDB connection and collection access for BraeloDB.
Database: BraeloDB @ localhost:27017 (configurable via MONGO_URI / MONGO_DB_NAME).
Collections: users, ad_packages, businesses, knowledge_base (region-wise), chat_history, contact_tracking.
"""
from django.conf import settings

_client = None


def get_client():
    """Return pymongo MongoClient (singleton)."""
    global _client
    if _client is None:
        try:
            from pymongo import MongoClient
            _client = MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000,
            )
            _client.admin.command("ping")
        except Exception as e:
            raise RuntimeError(f"MongoDB connection failed: {e}") from e
    return _client


def get_db():
    """Return BraeloDB database."""
    return get_client()[settings.MONGO_DB_NAME]


def get_collection(name: str):
    """Return collection by name (users, ad_packages, businesses, knowledge_base, chat_history, contact_tracking)."""
    return get_db()[name]


def ensure_indexes():
    """Create indexes for efficient queries (state, region, county, category, etc.)."""
    db = get_db()
    db.knowledge_base.create_index([("state", 1), ("county", 1)])
    db.knowledge_base.create_index("state")
    db.knowledge_base.create_index("region")
    db.knowledge_base.create_index("document_source")
    db.businesses.create_index([("state", 1), ("county", 1), ("category", 1)])
    db.businesses.create_index("category")
    db.users.create_index("external_id", unique=True)
