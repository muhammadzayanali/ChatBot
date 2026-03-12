# Client Requirements Implementation

This document maps the client’s requirements to the current Braelo Django backend (RAG + LLM, OpenAI, vector-style search).

---

## 1. Response behavior

| Requirement | Implementation |
|-------------|----------------|
| Respond **only** from internal knowledge base | `generate_rag_response()` in `chat/services/gpt_service.py` uses strict system prompt: "ONLY use information from the provided context". RAG path in `chat_flow.py` only passes retrieved chunks as context. |
| No external information, no guessing | Same strict prompt: "NEVER use external knowledge or guess". If context is empty or no match, we say we don’t have that information and ask to rephrase or share location. |
| No bullet points or dashes | All prompts (RAG, translation, clarifying, business reply) instruct: "NEVER use bullet points (•), dashes (-)". `_format_businesses_flowing()` builds flowing text only. |
| No overly technical language | Prompt: "Use simple language. Avoid legal jargon or overly technical terms." |
| No going out of context | RAG answer is generated only from `retrieved_context`; no free-form generation beyond that. |
| Don’t guess if unclear | Intent `unclear` or low confidence → `generate_clarifying_questions()`. No answer generated from guess. |
| Ask clarifying questions as needed | `generate_clarifying_questions(message, language, missing_location=True/False)` in GPT service; used when intent is unclear or location is incomplete. |
| Clear, direct, objective when question is clear | Strict RAG + tone instructions: "Concise but complete; no unnecessary explanations." |

---

## 2. Location

| Requirement | Implementation |
|-------------|----------------|
| Always know user’s state, county, ZIP | `User` model: `state`, `county`, `zip_code`. Request body can send `state`, `county`, `zip_code`; stored via `get_or_create_user(..., location)`. |
| Cross-match user ZIP with database | Business matching filters by `state`, `county`, `zip_code`; optional distance via `geopy` when lat/lon exist. |
| If location off, limit communication | `location_enabled` on User; when `False`, response is a single message asking to enable location. |
| Location required for relevance | Non-casual intents require state + county + zip; otherwise we return clarifying questions asking for them. |

---

## 3. Tone and style

| Requirement | Implementation |
|-------------|----------------|
| Emotional and welcoming; professional/formal when appropriate | System prompt: "Emotional and welcoming by default; professional and formal when the situation calls for it." |
| Avoid unnecessary explanations; no excess information | "Concise but complete; no unnecessary explanations." |
| No closing statements; keep conversation open | Prompt: "NEVER add closing statements like 'Let me know if you need help'. Keep the conversation open." Applied in RAG, translation, and generic reply. |

---

## 4. Business listings

| Requirement | Implementation |
|-------------|----------------|
| List businesses + brief explanation at end | `_format_businesses_flowing()`: list in prose, then a single sentence (e.g. "These providers serve your area..."). |
| Always prioritize sponsored businesses | `get_top_businesses()` sorts by `ad_package` priority first, then distance, then rotation. |
| 3–5 businesses per response | `MIN_BUSINESS_RESULTS` / `MAX_BUSINESS_RESULTS` in settings; default 3–5. |
| “See more…” link | `see_more` flag when more than `limit` results exist; returned in API and appended in flowing text. |
| If no exact match, show closest and state it | When no business within primary radius, we take results within fallback radius and set `location_note`: "No exact matches in your area. Here are the closest available options." |
| Rotation so same businesses aren’t always shown | `Business.rotation_index`; ranking uses it so eligible businesses get visibility over time. |
| Answers by state; ads/businesses can add WhatsApp | Knowledge base filtered by state (and optional county). `Business.whatsapp_url`; returned in API for "Contact via WhatsApp" button. |

---

## 5. Contact and tracking

| Requirement | Implementation |
|-------------|----------------|
| Contact free; no monetization per contact | No billing logic; contact is just tracked. |
| “Contact via WhatsApp” button to measure contact intentions | `POST /api/track-contact` with `business_id`, `contact_type` (whatsapp/phone/email). `ContactTracking` model stores each event. |
| Track contact intentions | `ContactTracking`: user/business, `contact_type`, timestamp. |

---

## 6. Accounts and history

| Requirement | Implementation |
|-------------|----------------|
| All users must create account for history and analysis | `User` is keyed by `external_id` (from session/auth). Chat history and location are stored per user. Frontend can enforce login and send `user_id` + location. |

---

## 7. Business comparison

| Requirement | Implementation |
|-------------|----------------|
| Compare 2–3 businesses; defined comparison responses | Intent `business_comparison`; `generate_business_comparison()` in GPT service with business context; response in flowing paragraphs (no bullets). |

---

## 8. Ban and verification (future)

| Requirement | Implementation |
|-------------|----------------|
| Ban policies; business verification | `User.is_banned`, `Business.is_banned`. No enforcement in API yet; can be added in middleware or view. |

---

## 9. Sponsorship suggestions

| Requirement | Implementation |
|-------------|----------------|
| Suggest sponsorship when appropriate; proactive ideas | Not yet implemented. Can be added in chat_flow after business_search (e.g. after N business queries in session). |

---

## 10. Service categories

| Requirement | Implementation |
|-------------|----------------|
| Service categories as main anchor | Intent extraction returns `category` / `subcategory`; business matching filters by them. |

---

## 11. Geographic distance

| Requirement | Implementation |
|-------------|----------------|
| Minimum metric: geographic distance within radius | `get_top_businesses()` uses `geopy` when user and business have lat/lon; `BUSINESS_RADIUS_MILES` (e.g. 25) and `BUSINESS_RADIUS_FALLBACK_MILES` (e.g. 50). |

---

## 12. Knowledge base and DOCX

| Requirement | Implementation |
|-------------|----------------|
| Answers from DOCX by state; Spanish → English | `load_docx` management command: loads "Respostas {State}.docx" and "Lista de Perguntas - IA.docx". `--translate` uses OpenAI to translate answers to English before storing. |
| County / document source | `KnowledgeBase.county`, `KnowledgeBase.document_source`; search can filter by county; document_source set on load. |

---

## API summary

- **POST /api/chat**  
  Body: `message` (or `msg`), optional `user_id`, `session_id`, and location: `state`, `county`, `zip_code`, `location_enabled`, `latitude`, `longitude`.  
  Response: `response`, `detected_language`, `businesses`, `intent`, `see_more`, `location_note`.

- **POST /api/track-contact**  
  Body: `business_id`, optional `contact_type` (whatsapp|phone|email), `user_id`.

- **GET /api/health**, **GET /api/debug/knowledge**  
  Unchanged.

---

## Running

```bash
cd backend
python manage.py migrate
python manage.py load_docx --translate   # load DOCX and translate answers to English
python manage.py runserver 5000
```

Optional: install `geopy` for distance-based business matching when lat/lon are available.
