"""
Application configuration. Use environment variables or .env for secrets.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Database: SQLite for dev; set DATABASE_URL for MySQL in production
# Example MySQL: mysql+pymysql://user:pass@localhost/braelo
_db_path = BASE_DIR / "braelo.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{str(_db_path).replace(chr(92), '/')}")

# Supported languages
SUPPORTED_LANGUAGES = ["en", "es", "pt"]
LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "pt": "Portuguese"}

# GPT
GPT_MODEL = os.environ.get("GPT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
KNOWLEDGE_SIMILARITY_THRESHOLD = float(os.environ.get("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.62"))
MAX_BUSINESS_RECOMMENDATIONS = 5

# Optional
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")

# Path to DOCX data (project root or backend/data)
DOCX_DATA_DIR = Path(os.environ.get("DOCX_DATA_DIR", BASE_DIR.parent))
