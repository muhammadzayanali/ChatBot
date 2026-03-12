# Testing the Braelo Chatbot (Django)

This guide uses a **test user and test businesses** with static location so the chatbot returns proper RAG answers and business results without you sending location every time.

---

## 1. Setup

### 1.1 API key

- Create `backend/.env` if it doesn’t exist.
- Add:
  ```env
  OPENAI_API_KEY=sk-your-actual-openai-key
  ```

### 1.2 DOCX files (for RAG)

- Put **Lista de Perguntas - IA.docx** and **Respostas Arizona.docx** (and other state DOCX if you have them) in the **project root** (folder that contains `backend/` and `frontend/`).

---

## 2. One-time setup: migrate, load knowledge, seed test data

Run these in order (from the `backend` folder):

```bash
cd backend

# Apply migrations
python manage.py migrate

# Load Q&A from DOCX into knowledge base (optional: --translate to store answers in English)
python manage.py load_docx --translate

# Seed test user + businesses with static location (Arizona, Maricopa, Phoenix, lat/lng)
python manage.py seed_test_data
```

**What `seed_test_data` creates:**

- **Test user** `test-user` with:
  - State: Arizona, County: Maricopa, ZIP: 85001, City: Phoenix
  - Latitude/Longitude: 33.4484, -112.0740 (Phoenix area)
  - `location_enabled`: true

- **4 test businesses** in the same area (legal, tax, immigration, housing) with lat/lng and contact/WhatsApp. One is sponsored (Premium).

After this, use **`user_id` or `session_id` = `"test-user"`** in chat requests so the backend uses this user’s saved location and returns proper RAG and business results.

---

## 3. Start the backend

```bash
cd backend
python manage.py runserver 5000
```

Base URL: **http://localhost:5000**

---

## 4. Quick checks

**Health**

```bash
curl http://localhost:5000/api/health
```

Expected: `{"status":"ok","llm":true}`

**Knowledge base**

```bash
curl http://localhost:5000/api/debug/knowledge
```

Check: `knowledge_base_total` > 0, `openai_key_set`: true.

---

## 5. Test chat (use test user so location is set)

### 5.1 Casual (greeting)

```bash
curl -X POST http://localhost:5000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Hello\", \"user_id\": \"test-user\"}"
```

(On Linux/Mac use `\` at end of line and `"{\"message\": \"Hello\", \"user_id\": \"test-user\"}"` in one line.)

Expected: Short greeting, no location prompt (test user has location).

---

### 5.2 Information question (RAG from knowledge base)

```bash
curl -X POST http://localhost:5000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"How does credit work for renting a place?\", \"user_id\": \"test-user\"}"
```

Expected: `intent`: `"information_request"`, `response`: answer based on your DOCX content for Arizona (no bullets, no closing phrase). If you don’t have DOCX loaded, you may get “I don’t have specific information…”.

---

### 5.3 Business search (should return test businesses)

```bash
curl -X POST http://localhost:5000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"I need a lawyer in Phoenix\", \"user_id\": \"test-user\"}"
```

Expected: `intent`: `"business_search"`, `businesses`: list with at least one (e.g. “Desert Legal Group”). Response text in flowing paragraphs; may include `see_more` and/or `location_note`.

Try also:

- “Find me a tax preparer”
- “Immigration help in Arizona”
- “Real estate agent in Maricopa”

---

### 5.4 With location in body (optional; overrides for that request)

You can send location in the body instead of using the test user:

```bash
curl -X POST http://localhost:5000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Find me a lawyer\", \"session_id\": \"any-id\", \"state\": \"Arizona\", \"county\": \"Maricopa\", \"zip_code\": \"85001\", \"location_enabled\": true}"
```

---

### 5.5 Contact tracking (WhatsApp button)

After a business search, use a returned `business_id` (e.g. `1`):

```bash
curl -X POST http://localhost:5000/api/track-contact ^
  -H "Content-Type: application/json" ^
  -d "{\"business_id\": 1, \"contact_type\": \"whatsapp\", \"user_id\": \"test-user\"}"
```

Expected: `{"status":"ok"}`.

---

## 6. Test without test user (location required)

If you use a different `user_id` (e.g. `"other-user"`) and do **not** send location in the body:

- First message may get a reply asking for **state, county, and ZIP**.
- Send a second message with location in the body, or create another seed user and use that `user_id`.

---

## 7. Frontend testing

1. Start backend: `cd backend && python manage.py runserver 5000`
2. Start frontend: `cd frontend && npm run dev`
3. In the app, if your frontend sends **user_id** and **session_id**:
   - Use `test-user` as the logged-in user (or send `state`, `county`, `zip_code` in the chat API request body).
4. Ask an info question and a business question; you should get RAG answers and business list for the Phoenix/Arizona test data.

---

## 8. Troubleshooting

| Issue | What to do |
|-------|------------|
| “I need your state, county, ZIP” for test-user | Run `python manage.py seed_test_data` again. Ensure you use `"user_id": "test-user"` (or `session_id`) in the request. |
| No businesses in response | Run `seed_test_data`. Check that businesses exist: Django admin or `GET /api/debug/knowledge` (only confirms KB; for businesses check DB or admin). |
| Generic “I don’t have specific information” | Load DOCX: `python manage.py load_docx --translate`. Confirm with `GET /api/debug/knowledge` that `knowledge_base_total` > 0. |
| `openai_key_set: false` | Set `OPENAI_API_KEY` in `backend/.env` and restart the server. |

---

## Quick checklist

| Step | Command / action | Verify |
|------|------------------|--------|
| 1 | `OPENAI_API_KEY` in `backend/.env` | `GET /api/health` → `"llm": true` |
| 2 | DOCX in project root | `python manage.py load_docx --translate` prints “Inserted N rows” |
| 3 | Seed test data | `python manage.py seed_test_data` → “Created/Updated test user”, “Created/Updated business” |
| 4 | Start server | `python manage.py runserver 5000` |
| 5 | Info question with test-user | `POST /api/chat` with `"user_id": "test-user"` and an info question → RAG-style answer |
| 6 | Business search with test-user | `POST /api/chat` with `"user_id": "test-user"` and “Find a lawyer” → `businesses` list |
| 7 | Track contact | `POST /api/track-contact` with `business_id` → `{"status":"ok"}` |

---

## Copy-paste testing (Windows PowerShell)

Backend must be running: `python manage.py runserver 5000`

**1. Health**
```powershell
curl http://localhost:5000/api/health
```

**2. Debug knowledge**
```powershell
curl http://localhost:5000/api/debug/knowledge
```

**3. Chat – greeting (test-user)**
```powershell
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"message\": \"Hello\", \"user_id\": \"test-user\"}"
```

**4. Chat – info question (RAG, test-user)**
```powershell
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"message\": \"How does credit work for renting?\", \"user_id\": \"test-user\"}"
```

**5. Chat – business search (test-user)**
```powershell
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"message\": \"I need a lawyer in Phoenix\", \"user_id\": \"test-user\"}"
```

**6. Track contact (use a business id from the previous response, e.g. 1)**
```powershell
curl -X POST http://localhost:5000/api/track-contact -H "Content-Type: application/json" -d "{\"business_id\": 1, \"contact_type\": \"whatsapp\", \"user_id\": \"test-user\"}"
```
