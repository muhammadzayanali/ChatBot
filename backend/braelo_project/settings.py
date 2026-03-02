"""
Django settings for Braelo project.
Loads configuration from .env file (same pattern as the Flask config.py).
"""
import os
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv()  # also from cwd
except ImportError:
    pass

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "chat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF disabled for API — we use csrf_exempt on views
    # "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "braelo_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "braelo_project.wsgi.application"

# Database
# SQLite for dev; set DATABASE_URL for production
_db_path = BASE_DIR / "braelo.db"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(_db_path),
    }
}

# If DATABASE_URL is set and starts with mysql, use MySQL
_database_url = os.environ.get("DATABASE_URL", "")
if _database_url.startswith("mysql"):
    # Parse: mysql+pymysql://user:pass@host/dbname
    import re
    m = re.match(r"mysql(?:\+\w+)?://([^:]+):([^@]+)@([^/]+)/(.+)", _database_url)
    if m:
        DATABASES["default"] = {
            "ENGINE": "django.db.backends.mysql",
            "USER": m.group(1),
            "PASSWORD": m.group(2),
            "HOST": m.group(3),
            "NAME": m.group(4),
            "OPTIONS": {"charset": "utf8mb4"},
        }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_ALL_ORIGINS = True  # fallback: allow all during dev
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
CORS_ALLOW_HEADERS = ["content-type", "authorization"]

# ---------------------------------------------------------------------------
# Braelo custom settings (from Flask config.py)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SUPPORTED_LANGUAGES = ["en", "es", "pt"]
LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "pt": "Portuguese"}

GPT_MODEL = os.environ.get("GPT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
KNOWLEDGE_SIMILARITY_THRESHOLD = float(os.environ.get("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.62"))
MAX_BUSINESS_RECOMMENDATIONS = 5

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")

# Path to DOCX data (project root or backend/data)
DOCX_DATA_DIR = Path(os.environ.get("DOCX_DATA_DIR", BASE_DIR.parent))
