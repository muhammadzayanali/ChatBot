"""
Chat flow: language detection -> GPT structured output -> knowledge search or business matching -> response.
"""
import json
from config import OPENAI_API_KEY, MAX_BUSINESS_RECOMMENDATIONS
from database.models import SessionLocal, ChatHistory, User
from services.language_detection import detect_language
from services.gpt_service import get_structured_output, generate_response
from services.knowledge_service import search_knowledge
from services.business_matching import get_top_businesses


def get_or_create_user(external_id: str, db) -> User:
    u = db.query(User).filter(User.external_id == external_id).first()
    if u:
        return u
    u = User(external_id=external_id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def format_businesses_for_reply(businesses: list, language: str) -> str:
    if not businesses:
        return ""
    lang_heading = {"en": "Local businesses you might find helpful:", "es": "Negocios locales que podrían ayudarte:", "pt": "Negócios locais que podem ajudar:"}
    heading = lang_heading.get(language, lang_heading["en"])
    lines = [heading, ""]
    for b in businesses:
        name = b.get("name", "")
        cat = b.get("category") or b.get("subcategory") or ""
        loc = [b.get("city"), b.get("state")] if b.get("city") or b.get("state") else []
        loc_str = ", ".join(filter(None, loc))
        contact = b.get("contact_info") or ""
        lines.append(f"• {name}" + (f" ({cat})" if cat else "") + (f" - {loc_str}" if loc_str else ""))
        if contact:
            lines.append(f"  Contact: {contact}")
    return "\n".join(lines)


def process_message(message: str, user_id: str = None, session_id: str = None) -> dict:
    """
    Main pipeline. Returns dict: response, detected_language, businesses, intent.
    """
    user_id = user_id or session_id or "anonymous"
    db = SessionLocal()
    try:
        # 1) Language detection
        detected_lang = detect_language(message)
        # 2) GPT structured output
        structured = get_structured_output(message) if OPENAI_API_KEY else {
            "intent": "information_request",
            "category": None,
            "subcategory": None,
            "state": None,
            "city": None,
            "detected_language": detected_lang,
        }
        if structured.get("detected_language"):
            detected_lang = structured["detected_language"]
        intent = structured.get("intent") or "information_request"
        category = structured.get("category")
        subcategory = structured.get("subcategory")
        state = structured.get("state")
        city = structured.get("city")

        # 3) Build reply
        knowledge_answer = None
        if intent == "information_request":
            matches = search_knowledge(message, state, db, limit=3)
            if matches:
                knowledge_answer = matches[0]["answer"]

        reply = generate_response(
            user_message=message,
            context="",
            language=detected_lang,
            knowledge_answer=knowledge_answer,
            businesses_text=None,
        )

        businesses = []
        if intent == "business_search" and OPENAI_API_KEY:
            businesses = get_top_businesses(
                category=category,
                subcategory=subcategory,
                state=state,
                city=city,
                language=detected_lang,
                limit=MAX_BUSINESS_RECOMMENDATIONS,
                external_id=user_id,
                session_id=session_id,
            )
            if businesses:
                reply = reply + "\n\n" + format_businesses_for_reply(businesses, detected_lang)

        # 4) Save chat history
        try:
            user = get_or_create_user(user_id, db)
            for role, content in [("user", message), ("assistant", reply)]:
                ch = ChatHistory(
                    user_id=user.id,
                    external_id=user_id,
                    role=role,
                    content=content,
                    intent=intent,
                    entities_json=json.dumps(structured) if structured else None,
                )
                db.add(ch)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": businesses,
            "intent": intent,
        }
    finally:
        db.close()
