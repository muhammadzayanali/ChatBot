# Flask → Django Conversion Verification

This document confirms that the Braelo backend has been **fully converted from Flask to Django**. Use Django as the single backend; the Flask app is deprecated.

---

## 1. Route & endpoint parity

| Flask (app.py) | Django (chat/views.py + chat/urls.py) | Status |
|----------------|--------------------------------------|--------|
| `GET /` | `path("", views.home)` → `home()` | ✅ Same: render template or fallback message |
| `POST /api/chat` | `path("api/chat", views.api_chat)` → `api_chat()` | ✅ Same: JSON body `message`/`msg`, returns `response`, `detected_language`, `businesses`, `intent` |
| `POST /get` | `path("get", views.legacy_get)` → `legacy_get()` | ✅ Same: form/JSON `msg`, plain text or JSON response |
| `GET /api/health` | `path("api/health", views.health)` → `health()` | ✅ Same: `{"status":"ok","llm":bool}` |
| `GET /api/debug/knowledge` | `path("api/debug/knowledge", views.debug_knowledge)` → `debug_knowledge()` | ✅ Same: knowledge_base counts and sample questions |
| Trailing slash (`/api/chat/`, `/get/`, etc.) | Explicit paths with trailing slash in urls.py | ✅ Supported |

---

## 2. Behaviour parity

- **CORS**: Flask used `@before_request` / `@after_request`; Django uses `django-cors-headers` in settings (CORS_ALLOW_ALL_ORIGINS / CORS_ALLOWED_ORIGINS).
- **OPTIONS**: Both handle OPTIONS for POST routes (Flask in `handle_preflight`, Django returns 200 for OPTIONS in views).
- **Legacy Keras/intents**: Both load `chatbot_model.h5`, `intents.json`, `words.pkl`, `classes.pkl` when `OPENAI_API_KEY` is not set and use the same logic for “my name is” / “hi my name is” and intent prediction.
- **LLM flow**: Flask used `chat_flow.process_message` (root `chat_flow.py` + `database.models` + `services/*`). Django uses `chat.chat_flow.process_message` with `chat.models` and `chat.services.*`.

---

## 3. Module mapping (Flask → Django)

| Flask | Django | Notes |
|-------|--------|--------|
| `config.py` | `braelo_project/settings.py` | OPENAI_API_KEY, DATABASE_URL, GPT_MODEL, EMBEDDING_MODEL, KNOWLEDGE_SIMILARITY_THRESHOLD, MAX_BUSINESS_RECOMMENDATIONS, SUPPORTED_LANGUAGES, DOCX_DATA_DIR, etc. |
| `database/models.py` (SQLAlchemy) | `chat/models.py` (Django ORM) | User, ChatHistory, KnowledgeBase, AdPackage, Business, ImpressionsLog, Lead |
| `chat_flow.py` (root) | `chat/chat_flow.py` | Same pipeline: casual intents → language detection → GPT/knowledge/business → response |
| `services/language_detection.py` | `chat/services/language_detection.py` | Uses `django.conf.settings` |
| `services/gpt_service.py` | `chat/services/gpt_service.py` | Uses `django.conf.settings` |
| `services/knowledge_service.py` | `chat/services/knowledge_service.py` | Uses Django ORM `KnowledgeBase` |
| `services/business_matching.py` | `chat/services/business_matching.py` | Uses Django ORM `Business`, `AdPackage`, `ImpressionsLog` |
| `services/casual_intents.py` | `chat/services/casual_intents.py` | File-based; same logic |
| `scripts/load_docx_to_knowledge.py` | `chat/management/commands/load_docx.py` | Run with `python manage.py load_docx` instead of the script |

---

## 4. Database

- **Flask**: SQLAlchemy + `database/models.py` + `init_db()`, `SessionLocal`, same SQLite/MySQL via `config.DATABASE_URL`.
- **Django**: Django ORM + `chat/models.py`, migrations in `chat/migrations/`, same SQLite default and optional MySQL via `DATABASE_URL` in settings.

Use only Django migrations and Django ORM for the app. Do not run Flask’s `init_db()` for the main app.

---

## 5. How to run (Django only)

```bash
cd backend
python manage.py migrate
python manage.py load_docx   # optional: load DOCX knowledge base
python manage.py runserver 5000
```

- API base: `http://localhost:5000` (or `http://127.0.0.1:5000`).
- Endpoints: `/`, `/api/chat`, `/api/chat/`, `/get`, `/get/`, `/api/health`, `/api/health/`, `/api/debug/knowledge`, `/api/debug/knowledge/`.
- Frontend: point to `http://localhost:5000` (e.g. `API_BASE_URL = 'http://localhost:5000'`).

---

## 6. Deprecated / no longer used for the app

- **`app.py`** (Flask): Kept only for reference. Do not run for new development; use Django.
- **`database/models.py`** and **`database/__init__.py`**: SQLAlchemy; replaced by `chat/models.py`.
- **`chat_flow.py`** (root): Replaced by `chat/chat_flow.py`.
- **`services/*`** (root): Replaced by `chat/services/*`.
- **`scripts/load_docx_to_knowledge.py`**: Replaced by `python manage.py load_docx`.

---

## 7. Verification checklist

- [x] All Flask routes have a Django view with the same URL and method.
- [x] Request/response formats match (JSON for `/api/chat`, form/JSON for `/get`, plain or JSON response where applicable).
- [x] CORS and OPTIONS are handled in Django.
- [x] Config and env vars are in Django settings.
- [x] All DB models are in Django ORM with equivalent fields and behaviour.
- [x] Chat flow (LLM + legacy) is implemented in `chat/chat_flow.py` and `chat/views.py`.
- [x] Knowledge loading is available via `python manage.py load_docx`.
- [x] Health and debug endpoints behave the same as in Flask.

**Conclusion: The backend is fully converted to Django. Run and verify using Django only.**
