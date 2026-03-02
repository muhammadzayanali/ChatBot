# Testing the Braelo Chatbot (Client Requirement)

Follow these steps to test so that questions from the client documents (e.g. **Respostas Arizona.docx**) return the **actual answer** from the document, not the generic message.

---

## Step 1: Check the setup

### 1.1 API key

- Create `backend/.env` if it doesn’t exist.
- Add one line:
  ```env
  OPENAI_API_KEY=sk-your-actual-openai-key
  ```
- Do **not** put the key inside `config.py`; use only `.env`.

### 1.2 DOCX location

- Put **Respostas Arizona.docx** in the **project root** (the folder that **contains** the `backend` folder).
- Example:
  ```
  chat bot/           <-- project root
  ├── backend/
  ├── frontend/
  └── Respostas Arizona.docx
  ```
- In the DOCX, the question and answer should be in **separate paragraphs**:
  - Paragraph 1: `Como funciona o crédito para alugar imóvel?`
  - Paragraph 2: The full answer text.

---

## Step 2: Load the knowledge base

From a terminal:

```bash
cd "D:\vs code program\python\chat bot\backend"
python scripts/load_docx_to_knowledge.py
```

- You should see something like:
  - `Using data dir: D:\vs code program\python\chat bot`
  - `Arizona: N entries`
  - `Done. Inserted N rows into knowledge_base.`
- If you see `No DOCX data found`, the DOCX is not in the expected folder or name.
- **Important:** Run this with `OPENAI_API_KEY` set in `.env` so embeddings are created. If the key is missing, rows are still inserted but without embeddings (text fallback will still work for exact/similar questions).

---

## Step 3: Verify the knowledge base (debug endpoint)

With the Flask server running (`python app.py`), open in the browser or with curl:

**URL:** `http://localhost:5000/api/debug/knowledge`

You should see JSON like:

```json
{
  "knowledge_base_total": 5,
  "knowledge_base_with_embeddings": 5,
  "sample_questions": [
    { "q": "Como funciona o crédito para alugar imóvel?", "state": "Arizona" }
  ],
  "openai_key_set": true
}
```

- If `knowledge_base_total` is **0**, run Step 2 again and fix the DOCX path/name.
- If `openai_key_set` is **false**, fix `backend/.env` and restart the server.

---

## Step 4: Restart the Flask server

After loading the knowledge base or changing `.env`:

1. Stop the server (Ctrl+C in the terminal where `python app.py` is running).
2. Start it again:
   ```bash
   cd backend
   python app.py
   ```

---

## Step 5: Test the chat (client requirement)

### 5.1 From the React app (http://localhost:5173)

1. Open the chat UI.
2. Send exactly: **Como funciona o crédito para alugar imóvel?**
3. **Expected:** The bot replies with the **answer from Respostas Arizona.docx** (possibly rephrased or translated by GPT), in Portuguese.
4. **Not expected:** The generic line: *"I'm here to help with questions about living in the USA and to connect you with local services..."*

### 5.2 From API (e.g. Postman or curl)

**Request:**

- URL: `http://localhost:5000/api/chat`
- Method: `POST`
- Headers: `Content-Type: application/json`
- Body (raw JSON):
  ```json
  {
    "message": "Como funciona o crédito para alugar imóvel?",
    "session_id": "test-session-1"
  }
  ```

**Expected response (conceptually):**

- `detected_language`: `"pt"` (or `"es"` if detected as Spanish).
- `intent`: `"information_request"`.
- `response`: The actual answer text from your document (possibly adapted by GPT), **not** the generic “I'm here to help...” message.

---

## Step 6: If you still get the generic message

1. **Check the server console** for:
   - `GPT generate_response failed: ...` → OpenAI API problem (key, quota, or network).
2. **Check the debug endpoint** again:
   - `GET http://localhost:5000/api/debug/knowledge`
   - Ensure `knowledge_base_total` > 0 and your question appears in `sample_questions` (or similar).
3. **Confirm DOCX format:**
   - Question paragraph ends with `?`
   - Answer is the **next** paragraph.
4. **Re-run the loader** after fixing DOCX or path:
   ```bash
   cd backend
   python scripts/load_docx_to_knowledge.py
   ```
   Then restart the server and test again.

---

## Quick checklist

| Step | What to do | How to verify |
|------|------------|----------------|
| 1 | Put `OPENAI_API_KEY` in `backend/.env` | `GET /api/debug/knowledge` → `openai_key_set: true` |
| 2 | Put `Respostas Arizona.docx` in project root | Loader prints "Arizona: N entries" and "Inserted N rows" |
| 3 | Run `python scripts/load_docx_to_knowledge.py` | No errors; "Done. Inserted N rows" |
| 4 | Open `GET /api/debug/knowledge` | `knowledge_base_total` ≥ 1, sample has your question |
| 5 | Restart Flask (`python app.py`) | Server starts without errors |
| 6 | Send "Como funciona o crédito para alugar imóvel?" in chat | Response is the document answer, not the generic message |
