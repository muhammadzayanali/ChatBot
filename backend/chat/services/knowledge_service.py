"""
Knowledge base: embeddings and semantic search over client DOCX Q&A.
Ported from Flask — uses django.conf.settings instead of config module.
"""
import json
import math
import unicodedata
from django.conf import settings

try:
    from openai import OpenAI
    _client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
except Exception:
    _client = None


def get_embedding(text: str) -> list:
    """Return embedding vector for text. Empty list if API unavailable."""
    if not text or not _client:
        return []
    try:
        r = _client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text.strip()[:8000])
        return r.data[0].embedding
    except Exception:
        return []


def cosine_similarity(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _normalize(s: str) -> str:
    """Lowercase and remove accents for text matching."""
    if not s:
        return ""
    s = s.strip().lower()
    n = unicodedata.normalize("NFD", s)
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def _words(s: str, min_len: int = 2) -> set:
    """Normalize and return set of significant words (letters only, min length)."""
    n = _normalize(s)
    words = set()
    for w in n.replace("?", " ").replace(".", " ").split():
        w = "".join(c for c in w if c.isalnum())
        if len(w) >= min_len:
            words.add(w)
    return words


def search_knowledge(query: str, state: str, limit: int = 5) -> list:
    """
    Semantic search over knowledge_base. Returns list of dicts with question, answer, state, similarity.
    Uses query embedding and cosine similarity; optionally filter by state.
    If no embedding match, falls back to text containment (query in question or question in query).

    Uses Django ORM instead of SQLAlchemy session.
    """
    from chat.models import KnowledgeBase
    from django.db.models import Q

    query_clean = _normalize(query or "")
    query_emb = get_embedding(query)

    # Get rows with embeddings
    qs = KnowledgeBase.objects.filter(embedding_json__isnull=False)
    if state:
        qs = qs.filter(Q(state=state) | Q(state__isnull=True))
    rows = list(qs)

    results = []
    if query_emb:
        for row in rows:
            try:
                emb = json.loads(row.embedding_json) if isinstance(row.embedding_json, str) else row.embedding_json
            except Exception:
                continue
            sim = cosine_similarity(query_emb, emb)
            if sim >= settings.KNOWLEDGE_SIMILARITY_THRESHOLD:
                results.append({
                    "question": row.question,
                    "answer": row.answer,
                    "state": row.state,
                    "similarity": round(sim, 4),
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        results = results[:limit]

    # Text fallback: exact/substring match, then word-overlap match
    if not results:
        all_qs = KnowledgeBase.objects.all()
        if state:
            all_qs = all_qs.filter(Q(state=state) | Q(state__isnull=True))
        rows_list = list(all_qs)
        query_words = _words(query or "")
        for row in rows_list:
            q_clean = _normalize(row.question or "")
            if not q_clean:
                continue
            # 1) Exact or substring match
            if query_clean in q_clean or q_clean in query_clean or query_clean == q_clean:
                results.append({"question": row.question, "answer": row.answer, "state": row.state, "similarity": 1.0})
                if len(results) >= limit:
                    break
                continue
            # 2) Word overlap: if most of the query words appear in the question, treat as match
            if query_words:
                q_words = _words(row.question or "")
                overlap = len(query_words & q_words) / len(query_words)
                if overlap >= 0.6:
                    results.append({"question": row.question, "answer": row.answer, "state": row.state, "similarity": round(overlap, 2)})
                    if len(results) >= limit:
                        break
        results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
