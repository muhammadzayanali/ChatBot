"""
GPT service: structured intent/entity extraction and conversational response.
"""
import json
import os
from openai import OpenAI
from config import OPENAI_API_KEY, GPT_MODEL, SUPPORTED_LANGUAGES, LANGUAGE_NAMES

client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

STRUCTURED_SCHEMA = {
    "intent": "information_request | business_search",
    "category": "e.g. legal, tax, housing",
    "subcategory": "e.g. lawyer, tax_preparer",
    "state": "US state or null",
    "city": "city or null",
    "detected_language": "en | es | pt",
}


def get_structured_output(message: str, conversation_summary: str = "") -> dict:
    """
    Call GPT to get intent and entities. Returns dict with intent, category, subcategory, state, city, detected_language.
    """
    if not client:
        return _fallback_structured(message)

    system = """You are an assistant for immigrant communities in the USA (Hispanic and Brazilian).
Your job is to classify the user message and extract structured data.
Respond with a JSON object only, no markdown, with these exact keys:
- intent: "information_request" if the user is asking for general information (immigration, housing, taxes, jobs, how to live in USA, etc.) OR "business_search" if they are looking for a local business/service (lawyer, tax preparer, doctor, etc.).
- category: one of legal, tax, housing, immigration, health, job, education, other (or null if not applicable).
- subcategory: more specific e.g. lawyer, tax_preparer, real_estate_agent, doctor (or null).
- state: US state name if mentioned (e.g. Florida, Texas, California) or null.
- city: city name if mentioned or null.
- detected_language: the language of the user message: "en" for English, "es" for Spanish, "pt" for Portuguese.
Use null for any field that is not clearly stated or not applicable."""

    user = f"User message: {message}"
    if conversation_summary:
        user += f"\n(Recent context: {conversation_summary})"

    try:
        resp = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        content = (resp.choices[0].message.content or "").strip()
        # strip code block if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(content)
        for key in ("intent", "category", "subcategory", "state", "city", "detected_language"):
            if key not in data:
                data[key] = None
        if data.get("detected_language") not in SUPPORTED_LANGUAGES:
            data["detected_language"] = "en"
        return data
    except Exception:
        return _fallback_structured(message)


def _fallback_structured(message: str) -> dict:
    return {
        "intent": "information_request",
        "category": None,
        "subcategory": None,
        "state": None,
        "city": None,
        "detected_language": "en",
    }


def generate_response(
    user_message: str,
    context: str,
    language: str,
    knowledge_answer: str = None,
    businesses_text: str = None,
) -> str:
    """
    Generate a final reply in the user's language. If knowledge_answer is provided, use it and optionally translate.
    If not, let GPT generate a helpful immigrant-focused answer. Append businesses_text if provided.
    """
    if not client:
        return _fallback_response(language, knowledge_answer, businesses_text)

    lang_name = LANGUAGE_NAMES.get(language, "English")
    system = f"""You are a helpful AI assistant for immigrant communities in the USA (Hispanic and Brazilian).
You provide accurate, verified information about living in the USA: immigration, housing, taxes, jobs, etc.
You MUST respond only in {lang_name}. Be concise and helpful."""

    if knowledge_answer:
        user = f"""Use this verified answer as the main content of your response. Translate or adapt it to {lang_name} if needed. Keep the same meaning and facts.
Verified answer:
{knowledge_answer}

User question was: {user_message}

Respond only in {lang_name}, nothing else."""
    else:
        user = f"""The user asked: {user_message}
If you have no verified answer, give a short helpful response in {lang_name} about living in the USA or suggest they ask more specifically. Respond only in {lang_name}."""

    try:
        resp = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.5,
        )
        reply = (resp.choices[0].message.content or "").strip()
        if businesses_text:
            reply = reply + "\n\n" + businesses_text
        return reply
    except Exception:
        return _fallback_response(language, knowledge_answer, businesses_text)


def _fallback_response(language: str, knowledge_answer: str = None, businesses_text: str = None) -> str:
    if knowledge_answer:
        out = knowledge_answer
    else:
        out = "I'm here to help with questions about living in the USA and to connect you with local services. Please ask in English, Spanish, or Portuguese."
    if businesses_text:
        out = out + "\n\n" + businesses_text
    return out
