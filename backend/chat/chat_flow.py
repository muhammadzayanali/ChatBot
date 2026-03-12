"""
Chat flow: strict RAG + location validation + intent (casual, information_request, business_search, business_comparison, unclear).
Responds only from internal knowledge base; no bullets/dashes; no closing statements; emotional/welcoming tone.
"""
import json
from django.conf import settings as django_settings
from chat.models import ChatHistory, User
from chat.services.language_detection import detect_language
from chat.services.gpt_service import (
    get_structured_output,
    generate_response,
    generate_rag_response,
    generate_clarifying_questions,
    generate_business_comparison,
    translate_verified_answer,
)
from chat.services.knowledge_service import search_knowledge
from chat.services.business_matching import get_top_businesses
from chat.services.casual_intents import get_casual_response


def _user_from_mongo(doc: dict):
    """Build a user-like object from MongoDB document for use in chat_flow."""
    class _UserLike:
        def __init__(self, d):
            self.external_id = d.get("external_id", "")
            self.language_preference = d.get("language_preference", "en")
            self.state = d.get("state")
            self.city = d.get("city")
            self.county = d.get("county")
            self.zip_code = d.get("zip_code")
            self.location_enabled = d.get("location_enabled", True)
            self.latitude = d.get("latitude")
            self.longitude = d.get("longitude")
            self.is_banned = d.get("is_banned", False)

        @property
        def has_complete_location(self):
            return bool(self.state and self.county and self.zip_code)

    return _UserLike(doc)


def get_or_create_user(external_id: str, location: dict = None):
    """Get or create user; optionally update location from request. Uses MongoDB when USE_MONGO is True."""
    if getattr(django_settings, "USE_MONGO", False):
        try:
            from chat.mongo_db import get_db
            from datetime import datetime
            db = get_db()
            col = db.users
            doc = col.find_one({"external_id": external_id})
            now = datetime.utcnow()
            if doc is None:
                doc = {
                    "external_id": external_id,
                    "language_preference": "en",
                    "state": None,
                    "city": None,
                    "county": None,
                    "zip_code": None,
                    "location_enabled": True,
                    "latitude": None,
                    "longitude": None,
                    "created_at": now,
                    "updated_at": now,
                    "is_banned": False,
                }
                if location:
                    doc["state"] = location.get("state")
                    doc["county"] = location.get("county")
                    doc["zip_code"] = location.get("zip_code")
                    doc["location_enabled"] = bool(location.get("location_enabled", True))
                    doc["latitude"] = location.get("latitude")
                    doc["longitude"] = location.get("longitude")
                col.insert_one(doc)
            elif location:
                update = {"updated_at": now}
                if location.get("state") is not None:
                    update["state"] = location["state"]
                if location.get("county") is not None:
                    update["county"] = location["county"]
                if location.get("zip_code") is not None:
                    update["zip_code"] = location["zip_code"]
                if "location_enabled" in location:
                    update["location_enabled"] = bool(location["location_enabled"])
                if location.get("latitude") is not None:
                    update["latitude"] = location["latitude"]
                if location.get("longitude") is not None:
                    update["longitude"] = location["longitude"]
                col.update_one({"external_id": external_id}, {"$set": update})
                doc = col.find_one({"external_id": external_id})
            return _user_from_mongo(doc)
        except Exception:
            return _user_from_mongo({
                "external_id": external_id,
                "state": location.get("state") if location else None,
                "county": location.get("county") if location else None,
                "zip_code": location.get("zip_code") if location else None,
                "location_enabled": location.get("location_enabled", True) if location else True,
                "latitude": location.get("latitude") if location else None,
                "longitude": location.get("longitude") if location else None,
            })

    user, _ = User.objects.get_or_create(external_id=external_id)
    if location:
        if "state" in location and location["state"]:
            user.state = location["state"]
        if "county" in location and location["county"]:
            user.county = location["county"]
        if "zip_code" in location and location["zip_code"]:
            user.zip_code = location["zip_code"]
        if "location_enabled" in location:
            user.location_enabled = bool(location["location_enabled"])
        if "latitude" in location and location["latitude"] is not None:
            user.latitude = location["latitude"]
        if "longitude" in location and location["longitude"] is not None:
            user.longitude = location["longitude"]
        user.save(update_fields=["state", "county", "zip_code", "location_enabled", "latitude", "longitude", "updated_at"])
    return user


def _looks_off_topic(message: str) -> bool:
    """Quick check for obvious off-topic requests (code, programming, etc.) so we always redirect."""
    if not message or len(message) > 500:
        return False
    lower = message.lower().strip()
    off_topic_patterns = (
        "code", "program", "c++", "c#", "python", "javascript", "java ",
        "for loop", "while loop", "algorithm", "script", "coding", "programming",
        "write me", "write the", "create a program", "debug", "syntax", "compile", "variable",
        "weather", "recipe", "joke", "tell me a joke", "sport", "movie", "game",
    )
    words = set(lower.split())
    for pattern in off_topic_patterns:
        if pattern in lower or pattern in words:
            return True
    return False


def _off_topic_message(language: str) -> str:
    """Friendly redirect when user asks outside scope (e.g. code, weather). In user's language."""
    messages = {
        "en": "I'm here to help with information about living in the USA and finding local businesses in your area. I can't help with that. What would you like to know about immigration, housing, taxes, or which type of business are you looking for?",
        "es": "Estoy aquí para ayudarte con información sobre vivir en EE.UU. y encontrar negocios locales en tu zona. No puedo ayudarte con eso. ¿Qué te gustaría saber sobre inmigración, vivienda, impuestos, o qué tipo de negocio buscas?",
        "pt": "Estou aqui para ajudar com informações sobre viver nos EUA e encontrar negócios locais na sua região. Não posso ajudar com isso. O que você gostaria de saber sobre imigração, moradia, impostos, ou que tipo de negócio você procura?",
    }
    return messages.get(language, messages["en"])


def _format_businesses_flowing(businesses: list, language: str, location_note: str = None, see_more: bool = False) -> str:
    """Format business list in flowing paragraphs (no bullets). Add brief explanation at end. Client requirement."""
    if not businesses:
        return ""
    lang_heading = {
        "en": "Here are some options that might help you:",
        "es": "Estas son algunas opciones que podrían ayudarte:",
        "pt": "Aqui estão algumas opções que podem ajudar:",
    }
    heading = lang_heading.get(language, lang_heading["en"])
    parts = [heading]
    for b in businesses:
        name = b.get("name", "")
        cat = b.get("category") or b.get("subcategory") or ""
        loc_parts = filter(None, [b.get("city"), b.get("county"), b.get("state")])
        loc_str = ", ".join(loc_parts)
        dist = b.get("distance_miles")
        dist_str = f" ({dist} miles away)" if dist is not None else ""
        line = name
        if cat:
            line += f", {cat}"
        if loc_str:
            line += f", in {loc_str}"
        line += dist_str
        if b.get("is_sponsored"):
            line += " (Sponsored)"
        parts.append(line)
        contact = b.get("contact_info") or ""
        whatsapp = b.get("whatsapp_url") or ""
        if contact or whatsapp:
            parts.append(f"Contact: {contact or whatsapp or 'See listing for details.'}")
    brief = {
        "en": "These providers serve your area and can assist with the service you asked about.",
        "es": "Estos proveedores sirven tu zona y pueden ayudarte con el servicio que buscas.",
        "pt": "Esses provedores atendem sua região e podem ajudar com o serviço que você precisa.",
    }
    parts.append("")
    parts.append(brief.get(language, brief["en"]))
    if location_note:
        parts.append("")
        parts.append(location_note)
    if see_more:
        more = {"en": "See more…", "es": "Ver más…", "pt": "Ver mais…"}
        parts.append(more.get(language, more["en"]))
    return "\n".join(parts)


def process_message(
    message: str,
    user_id: str = None,
    session_id: str = None,
    user_location: dict = None,
) -> dict:
    """
    Main pipeline. Requires location (state, county, zip_code) for full answers.
    Returns: response, detected_language, businesses, intent, see_more, location_note, question_analysis.
    """
    user_id = user_id or session_id or "anonymous"
    user_location = user_location or {}

    # Resolve user and location from DB if not in request
    user = get_or_create_user(user_id, user_location)
    state = user_location.get("state") or user.state
    county = user_location.get("county") or user.county
    zip_code = user_location.get("zip_code") or user.zip_code
    location_enabled = user_location.get("location_enabled", user.location_enabled)

    # 0) Casual: greetings, thanks, goodbye
    casual_text, casual_tag = get_casual_response(message)
    if casual_text:
        detected_lang = detect_language(message)
        if django_settings.OPENAI_API_KEY and detected_lang != "en":
            reply = translate_verified_answer(casual_text, detected_lang)
        else:
            reply = casual_text
        _save_history(user_id, message, reply, "casual", {"detected_language": detected_lang})
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "casual",
            "see_more": False,
            "location_note": None,
            "question_analysis": {"intent": "casual", "detected_language": detected_lang},
        }

    detected_lang = detect_language(message)
    structured = get_structured_output(message) if django_settings.OPENAI_API_KEY else {
        "intent": "information_request",
        "category": None,
        "subcategory": None,
        "state": None,
        "city": None,
        "county": None,
        "zip_code": None,
        "detected_language": detected_lang,
        "confidence": 0.5,
    }
    if structured.get("detected_language"):
        detected_lang = structured["detected_language"]
    intent = structured.get("intent") or "information_request"
    confidence = structured.get("confidence")
    if confidence is not None and float(confidence) < 0.6 and intent != "off_topic":
        intent = "unclear"

    # Keyword guardrail: force off_topic for obvious out-of-scope requests (code, programming, etc.)
    if _looks_off_topic(message):
        intent = "off_topic"

    # Location required: limit communication if off or incomplete
    if not location_enabled:
        reply = "To give you the most accurate answers, I need access to your location. Please enable location so I can help you with information for your area."
        if detected_lang != "en" and django_settings.OPENAI_API_KEY:
            reply = translate_verified_answer(reply, detected_lang)
        _save_history(user_id, message, reply, "location_required", structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "location_required",
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    if not state or not county or not zip_code:
        reply = generate_clarifying_questions(message, detected_lang, missing_location=True)
        _save_history(user_id, message, reply, "location_incomplete", structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "location_incomplete",
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    # Off-topic: restrict to chatbot scope (client requirement)
    if intent == "off_topic":
        reply = _off_topic_message(detected_lang)
        _save_history(user_id, message, reply, "off_topic", structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "off_topic",
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    # Unclear intent: ask clarifying questions
    if intent == "unclear":
        reply = generate_clarifying_questions(message, detected_lang, missing_location=False)
        _save_history(user_id, message, reply, "unclear", structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "unclear",
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    # Business comparison: 2–3 businesses
    if intent == "business_comparison":
        businesses_context = ""
        try:
            category = structured.get("category") or structured.get("subcategory")
            if getattr(django_settings, "USE_MONGO", False):
                try:
                    from chat.mongo_db import get_db
                    db = get_db()
                    q = {"is_active": True, "is_banned": {"$ne": True}}
                    if state:
                        q["state"] = {"$regex": state, "$options": "i"}
                    if category:
                        q["$or"] = [
                            {"category": {"$regex": category, "$options": "i"}},
                            {"subcategory": {"$regex": category, "$options": "i"}},
                        ]
                    for b in db.businesses.find(q).limit(5):
                        businesses_context += f"{b.get('name','')}: {b.get('category') or ''} {b.get('subcategory') or ''}, {b.get('city') or ''} {b.get('state') or ''}. {b.get('contact_info') or ''}\n"
                except Exception:
                    pass
            else:
                from chat.models import Business
                qs = Business.objects.filter(is_active=True, is_banned=False)
                if state:
                    qs = qs.filter(state__icontains=state)
                if category:
                    qs = qs.filter(category__icontains=category) | qs.filter(subcategory__icontains=category)
                for b in qs[:5]:
                    businesses_context += f"{b.name}: {b.category or ''} {b.subcategory or ''}, {b.city or ''} {b.state or ''}. {b.contact_info or ''}\n"
        except Exception:
            pass
        reply = generate_business_comparison(message, businesses_context or "No business data available.", detected_lang)
        _save_history(user_id, message, reply, "business_comparison", structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": "business_comparison",
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    # Information request: strict RAG only
    if intent == "information_request":
        county_q = county or structured.get("county")
        matches = search_knowledge(message, state=state, county=county_q)
        if not matches and state:
            matches = search_knowledge(message, state=None, county=None)
        context_parts = []
        for m in matches:
            context_parts.append(f"Q: {m.get('question', '')}\nA: {m.get('answer', '')}")
        retrieved_context = "\n\n".join(context_parts) if context_parts else ""
        reply = generate_rag_response(
            user_message=message,
            retrieved_context=retrieved_context,
            state=state,
            county=county,
            zip_code=zip_code,
            language=detected_lang,
        )
        _save_history(user_id, message, reply, intent, structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": [],
            "intent": intent,
            "see_more": False,
            "location_note": None,
            "question_analysis": structured,
        }

    # Business search: geographic match, 3–5 results, see more, closest available
    if intent == "business_search":
        limit = getattr(django_settings, "MAX_BUSINESS_RESULTS", 5)
        user_lat = user_location.get("latitude") or (user.latitude if user else None)
        user_lon = user_location.get("longitude") or (user.longitude if user else None)
        result = get_top_businesses(
            category=structured.get("category"),
            subcategory=structured.get("subcategory"),
            state=state,
            city=structured.get("city"),
            county=county,
            zip_code=zip_code,
            user_lat=user_lat,
            user_lon=user_lon,
            language=detected_lang,
            limit=limit,
            external_id=user_id,
            session_id=session_id or user_id,
        )
        businesses = result.get("businesses") or []
        see_more = result.get("see_more", False)
        location_note = result.get("location_note")
        reply = generate_response(
            user_message=message,
            context="",
            language=detected_lang,
            knowledge_answer=None,
            businesses_text=None,
        )
        if businesses:
            reply = _format_businesses_flowing(
                businesses,
                detected_lang,
                location_note=location_note,
                see_more=see_more,
            )
        else:
            reply = "I couldn't find businesses matching your criteria in your area. Try adjusting your request or your location."
            if detected_lang != "en" and django_settings.OPENAI_API_KEY:
                reply = translate_verified_answer(reply, detected_lang)
        _save_history(user_id, message, reply, intent, structured)
        return {
            "response": reply,
            "detected_language": detected_lang,
            "businesses": businesses,
            "intent": intent,
            "see_more": see_more,
            "location_note": location_note,
            "question_analysis": structured,
        }

    # Fallback
    reply = generate_response(message, "", detected_lang, knowledge_answer=None, businesses_text=None)
    _save_history(user_id, message, reply, intent, structured)
    return {
        "response": reply,
        "detected_language": detected_lang,
        "businesses": [],
        "intent": intent,
        "see_more": False,
        "location_note": None,
        "question_analysis": structured,
    }


def _save_history(user_id: str, message: str, reply: str, intent: str, structured: dict):
    try:
        if getattr(django_settings, "USE_MONGO", False):
            for role, content in [("user", message), ("assistant", reply)]:
                ChatHistory.objects.create(
                    user=None,
                    external_id=user_id,
                    role=role,
                    content=content,
                    intent=intent,
                    entities_json=json.dumps(structured) if structured else None,
                )
        else:
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
        pass
