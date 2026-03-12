# How to run the Braelo project

Follow these steps to run the backend and frontend so you can test the chatbot in the browser.

---

## 1. Backend (Django, port 5000)

### 1.1 Open a terminal and go to the backend folder

```bash
cd "d:\vs code program\python\chat bot\backend"
```

(Or from the project root: `cd backend`.)

### 1.2 Environment

- Create `backend/.env` if it doesn’t exist.
- Add your OpenAI key (required for RAG and business replies):

  ```env
  OPENAI_API_KEY=sk-your-actual-key
  ```

### 1.3 One-time setup (migrations, knowledge base, test data)

**Option A – Using MongoDB (BraeloDB)**  
If you use MongoDB at `localhost:27017` with database **BraeloDB**:

1. Ensure MongoDB is running (e.g. `mongod`).
2. In `backend/.env` set (optional; these are the defaults):
   ```env
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB_NAME=BraeloDB
   USE_MONGO=true
   ```
3. Install deps and load data into MongoDB:
   ```bash
   cd backend
   pip install pymongo
   python manage.py load_mongo_data --translate
   ```
   This seeds the **static/test data** (test user, ad package, 4 businesses) and loads **client DOCX** (e.g. `Respostas Arizona.docx`, `Respostas NY.docx`) **region-wise** into the `knowledge_base` collection. Put DOCX files in the **project root** (same as for `load_docx`).

**Option B – Using Django DB only (SQLite/MySQL)**  
Run these once (or after pulling changes / resetting the DB):

```bash
cd backend
python manage.py migrate
python manage.py load_docx --translate
python manage.py seed_test_data
```

- **migrate** – creates/updates DB tables.
- **load_docx** – loads Q&A from DOCX files (e.g. `Respostas Arizona.docx`) into the knowledge base. Put DOCX files in the **project root** (folder that contains `backend` and `frontend`). Use `--translate` to store answers in English.
- **seed_test_data** – creates a test user and test businesses with fixed location (Arizona, Maricopa, Phoenix) so the chat works without you entering location in the UI.

### 1.4 Start the backend server

```bash
cd backend
python manage.py runserver 5000
```

Leave this terminal open. The API will be at **http://127.0.0.1:5000**.

---

## 2. Frontend (Vite/React, port 5173)

### 2.1 Open a second terminal

### 2.2 Install dependencies (first time only)

```bash
cd "d:\vs code program\python\chat bot\frontend"
npm install
```

### 2.3 Start the frontend

```bash
cd frontend
npm run dev
```

The app will open at **http://localhost:5173** (or the URL shown in the terminal).

---

## 3. Test in the browser

1. Open **http://localhost:5173** (or the URL from `npm run dev`).
2. The chat is already wired to the backend with:
   - **Test user** and **static location** (Arizona, Maricopa, 85001) so you don’t need to enter location.
3. Try for example:
   - **Hello** – greeting.
   - **How does credit work for renting?** – RAG answer from the knowledge base (if DOCX was loaded).
   - **I need a lawyer in Phoenix** – list of test businesses (e.g. Desert Legal Group) with “Contact via WhatsApp” if available.
4. Clicking **Contact via WhatsApp** on a business sends a contact event to the backend (track-contact).

---

## 4. Quick checklist

**With MongoDB (BraeloDB):**

| Step | Command | Notes |
|------|--------|--------|
| 1 | `OPENAI_API_KEY=...` and `USE_MONGO=true` in `backend/.env` | Required for RAG; USE_MONGO uses BraeloDB |
| 2 | Start MongoDB (e.g. `mongod`) | Default: localhost:27017 |
| 3 | `cd backend` then `python manage.py load_mongo_data --translate` | One-time; seeds users/businesses + DOCX by region |
| 4 | `python manage.py runserver 5000` | Start backend (keep running) |
| 5 | `cd frontend` then `npm install` then `npm run dev` | Start frontend |
| 6 | Open http://localhost:5173 | Test chat in browser |

**With Django DB only (SQLite/MySQL):**

| Step | Command | Notes |
|------|--------|--------|
| 1 | `OPENAI_API_KEY=...` in `backend/.env` | Required for RAG and full replies |
| 2 | `cd backend` then `python manage.py migrate` | One-time |
| 3 | `python manage.py load_docx --translate` | One-time; needs DOCX in project root |
| 4 | `python manage.py seed_test_data` | One-time; creates test user + businesses |
| 5 | `python manage.py runserver 5000` | Start backend (keep running) |
| 6 | `cd frontend` then `npm install` then `npm run dev` | Start frontend |
| 7 | Open http://localhost:5173 | Test chat in browser |

---

## 5. If something doesn’t work

- **“Something went wrong” in chat**  
  - Backend must be running at **http://127.0.0.1:5000** (see step 1.4).  
  - Check `backend/.env` has a valid `OPENAI_API_KEY`.

- **No RAG answer / generic reply**  
  - Run `python manage.py load_docx --translate` and put the DOCX files in the project root.  
  - Check: `curl http://127.0.0.1:5000/api/debug/knowledge` and ensure `knowledge_base_total` > 0.

- **No businesses in the list**  
  - Run `python manage.py seed_test_data` in the backend folder.  
  - Ask e.g. “Find me a lawyer in Phoenix” or “I need a tax preparer”.

- **CORS errors in the browser**  
  - Backend uses `django-cors-headers` and allows `http://localhost:5173` and `http://127.0.0.1:5173`. If you use another origin, add it in `backend/braelo_project/settings.py` (`CORS_ALLOWED_ORIGINS` or keep `CORS_ALLOW_ALL_ORIGINS = True` for local dev).
