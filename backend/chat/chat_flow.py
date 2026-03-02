"""
Chat flow: casual intents -> language detection -> analyze question (GPT) -> knowledge search or business matching -> response.
Ported from Flask — uses Django ORM instead of SQLAlchemy sessions.
"""
import json
from django.conf import settings as django_settings
from chat.models import ChatHistory, User
from chat.services.language_detection import detect_language
from chat.services.gpt_service import get_structured_output, generate_response, translate_verified_answer
from chat.services.knowledge_service import search_knowledge
from chat.services.business_matching import get_top_businesses
from chat.services.casual_intents import get_casual_response


def get_or_create_user(external_id: str) -> User:
    """Get existing user or create a new one."""
    user, created = User.objects.get_or_create(external_id=external_id)
    return user


def format_businesses_for_reply(businesses: list, language: str) -> str:
    if not businesses:
        return ""
    lang_heading = {
        "en": "Local businesses you might find helpful:",
        "es": "Negocios locales que podrían ayudarte:",
        "pt": "Negócios locais que podem ajudar:",
    }
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
    Flow: (1) casual intent match (hi, bye, thanks, etc.) -> (2) analyze question -> (3) knowledge or business -> reply.
    """
    user_id = user_id or session_id or "anonymous"

    # 0) Casual conversation: greetings, goodbye, thanks, "what can you do", etc.
    casual_text, casual_tag = get_casual_response(message)
    if casual_text:
        detected_lang = detect_language(message)
        if django_settings.OPENAI_API_KEY and detected_lang != "en":
            reply = translate_verified_answer(casual_text, detected_lang)
        else:
            reply = casual_text
        try:
            user = get_or_create_user(user_id)
            for role, content in [("user", message), ("assistant", reply)]:
                ChatHistory.objects.create(
                    user=user,
                    external_id=user_id,
                    role=role,
                    content=content,
                    intent=casual_tag or "casual",
                    entities_json=json.dumps({"detected_language": detected_lang}),
                )
        except Exception:
            pass  # Don't fail the response if history save fails
        question_analysis = {
            "intent": casual_tag or "casual",
            "category": None,
            "subcategory": None,
            "state": None,
            "city": None,
            "detected_language": detected_lang,
        }
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": casual_tag or "casual",
            "question_analysis": question_analysis,
        }

    # 1) Language detection
    detected_lang = detect_language(message)
    # 2) Analyze question: GPT structured output (intent, category, state, etc.)
    structured = get_structured_output(message) if django_settings.OPENAI_API_KEY else {
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

    # 3) Build reply from client documents (knowledge base)
    knowledge_answer = None
    if intent == "information_request":
        matches = search_knowledge(message, state, limit=3)
        if not matches and state:
            matches = search_knowledge(message, None, limit=3)  # try without state filter
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
    if intent == "business_search" and django_settings.OPENAI_API_KEY:
        businesses = get_top_businesses(
            category=category,
            subcategory=subcategory,
            state=state,
            city=city,
            language=detected_lang,
            limit=django_settings.MAX_BUSINESS_RECOMMENDATIONS,
            external_id=user_id,
            session_id=session_id,
        )
        if businesses:
            reply = reply + "\n\n" + format_businesses_for_reply(businesses, detected_lang)

    # 4) Save chat history
    try:
        user = get_or_create_user(user_id)
        for role, content in [("user", message), ("assistant", reply)]:
            ChatHistory.objects.create(
                user=user,
                external_id=user_id,
                role=role,
                content=content,
                intent=intent,
                entities_json=json.dumps(structured) if structured else None,
            )
    except Exception:
        pass  # Don't fail the response if history save fails

    question_analysis = {
        "intent": intent,
        "category": category,
        "subcategory": subcategory,
        "state": state,
        "city": city,
        "detected_language": detected_lang,
    }
    return {
        "response": reply,
        "detected_language": detected_lang,
        "businesses": businesses,
        "intent": intent,
        "question_analysis": question_analysis,
    }
