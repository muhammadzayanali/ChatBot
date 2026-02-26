"""
Knowledge base: embeddings and semantic search over client DOCX Q&A.
"""
import json
import math
from config import EMBEDDING_MODEL, KNOWLEDGE_SIMILARITY_THRESHOLD

try:
    from openai import OpenAI
    from config import OPENAI_API_KEY
    _client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    _client = None


def get_embedding(text: str) -> list:
    """Return embedding vector for text. Empty list if API unavailable."""
    if not text or not _client:
        return []
    try:
        r = _client.embeddings.create(model=EMBEDDING_MODEL, input=text.strip()[:8000])
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


def search_knowledge(query: str, state: str, db_session, limit: int = 5) -> list:
    """
    Semantic search over knowledge_base. Returns list of dicts with question, answer, state, similarity.
    Uses query embedding and cosine similarity; optionally filter by state.
    """
    from database.models import KnowledgeBase

    query_emb = get_embedding(query)
    if not query_emb:
        return []

    rows = db_session.query(KnowledgeBase).filter(KnowledgeBase.embedding_json.isnot(None))
    if state:
        # match state or general (state is null)
        from sqlalchemy import or_
        rows = rows.filter(or_(KnowledgeBase.state == state, KnowledgeBase.state.is_(None)))
    rows = rows.all()

    results = []
    for row in rows:
        try:
            emb = json.loads(row.embedding_json) if isinstance(row.embedding_json, str) else row.embedding_json
        except Exception:
            continue
        sim = cosine_similarity(query_emb, emb)
        if sim >= KNOWLEDGE_SIMILARITY_THRESHOLD:
            results.append({
                "question": row.question,
                "answer": row.answer,
                "state": row.state,
                "similarity": round(sim, 4),
            })
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
