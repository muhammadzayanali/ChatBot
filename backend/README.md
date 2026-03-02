# Braelo Backend

LLM-based assistant for immigrant communities: GPT structured output, knowledge base from client DOCX files, business matching, and multilingual (EN/ES/PT) responses.

## Setup

1. Create a virtualenv and install deps:
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate    # Windows PowerShell
   pip install -r requirements.txt
   ```
   **If you get "Unable to create process using '...chatBot\\.venv\\Scripts\\python.exe'"**: your `.venv` was created when the project had a different path. Use a new venv: `python -m venv venv`, then `.\venv\Scripts\activate`, then `pip install -r requirements.txt`. Or run without activating: `python -m pip install -r requirements.txt`.

2. Copy `.env.example` to `.env` and set:
   ```bash
   OPENAI_API_KEY=sk-...
   ```

3. Initialize DB and load client DOCX into knowledge base:
   ```bash
   cd backend
   python scripts/load_docx_to_knowledge.py
   ```
   Place your DOCX files in the project root (parent of `backend/`):
   - `Lista de Perguntas - IA.docx` (questions list)
   - `Respostas Arizona.docx`, `Respostas Texas.docx`, etc. (state-specific answers)

4. (Optional) Add businesses for the matching engine: insert into `businesses` and `ad_packages` tables, or use an admin API later.

## Run

From the `backend` directory:
```bash
python app.py
```
Server runs at http://localhost:5000.

## API

- **POST /api/chat** – JSON body: `{ "message": "...", "session_id": "..." }`. Returns `{ "response", "detected_language", "businesses", "intent" }`.
- **POST /get** – Legacy form body: `msg=...`. Returns plain text response (uses same LLM flow when `OPENAI_API_KEY` is set).
- **GET /api/health** – `{ "status": "ok", "llm": true/false }`.

## Flow

1. Language detection (langdetect or GPT).
2. GPT returns structured intent + entities (category, state, city, etc.).
3. If **information_request**: semantic search over `knowledge_base` (embeddings from client DOCX); return stored answer in user language or GPT fallback.
4. If **business_search**: query `businesses`, rank by sponsored/impressions, return top 5 and log impressions.
5. Chat history and users stored in SQLite (or MySQL via `DATABASE_URL`).

## Troubleshooting: Bot returns generic message

If the bot always replies with *"I'm here to help with questions about living in the USA..."* instead of answers from your documents:

1. **Set the API key in `.env`** (not in code). In `backend/.env` add: `OPENAI_API_KEY=sk-your-actual-key`
2. **Put your DOCX in the project root** (folder that contains `backend/`): e.g. `Respostas Arizona.docx`. In each Respostas file you can have one question per paragraph (ending with `?`) and the next paragraph as the answer.
3. **Load the knowledge base** (run once, or after changing DOCX): `cd backend` then `python scripts/load_docx_to_knowledge.py`. You should see "Inserted N rows into knowledge_base."
4. **Restart the Flask server** (`python app.py`).
5. If it still fails, check the server console for `GPT generate_response failed:` to see API errors.
