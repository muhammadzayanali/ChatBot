"""
MongoDB connection and collection access for chatbot local DB.
Database: MONGO_DB_NAME @ MONGO_URI (e.g. BraeloDB @ localhost:27017).
Collections: users (chat), ad_packages, knowledge_base (with embedding vectors), chat_history, contact_tracking,
impressions_log; plus Braelo-format collections after sync: business_listings, vehicle_listing, chats, messages, etc.
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
    """Return chatbot MongoDB database (same DB holds Braelo data after sync)."""
    return get_client()[settings.MONGO_DB_NAME]


def get_collection(name: str):
    """Return collection by name."""
    return get_db()[name]


def ensure_indexes():
    """Create indexes for efficient queries. Safe if a collection does not exist yet."""
    db = get_db()
    # knowledge_base: RAG and region filters; embedding field used for vector similarity in-app
    try:
        db.knowledge_base.create_index([("state", 1), ("county", 1)])
        db.knowledge_base.create_index("state")
        db.knowledge_base.create_index("region")
        db.knowledge_base.create_index("document_source")
    except Exception:
        pass
    # business_listings: Braelo format (business_category, business_subcategory)
    try:
        db.business_listings.create_index("business_category")
        db.business_listings.create_index("business_subcategory")
        db.business_listings.create_index([("business_category", 1), ("business_subcategory", 1)])
        db.business_listings.create_index("is_active")
    except Exception:
        pass
    # Chatbot users (chat sessions)
    try:
        db.users.create_index("external_id", unique=True)
    except Exception:
        pass
