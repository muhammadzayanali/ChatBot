"""
GPT service: structured intent/entity extraction and conversational response.
Ported from Flask — uses django.conf.settings instead of config module.
"""
import json
import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)
client = None
if settings.OPENAI_API_KEY:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

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
            model=settings.GPT_MODEL,
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
        if data.get("detected_language") not in settings.SUPPORTED_LANGUAGES:
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


def translate_verified_answer(text: str, target_language: str) -> str:
    """
    Translate the verified answer to target language only. Do not summarize or rephrase.
    Preserve every line, bullet, and structure. Returns original text if translation fails.
    """
    if not client or not text or not text.strip():
        return text or ""
    lang_name = settings.LANGUAGE_NAMES.get(target_language, "English")
    system = f"""You are a translator. Your ONLY job is to translate the following text to {lang_name}.
Rules:
- Output the exact same structure: same line breaks, same bullets (•), same numbering.
- Do NOT add, remove, or rephrase any line. Do NOT summarize.
- Translate only. Output nothing else."""

    user = f"Translate this to {lang_name}:\n\n{text}"

    try:
        resp = client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out if out else text
    except Exception as e:
        logger.warning("GPT translate_verified_answer failed: %s", e)
        return text


def generate_response(
    user_message: str,
    context: str,
    language: str,
    knowledge_answer: str = None,
    businesses_text: str = None,
    translate_answer: bool = True,
) -> str:
    """
    Generate a final reply in the user's language.
    If knowledge_answer is provided: return it in full, only translating to user language if translate_answer=True.
    If not, let GPT generate a helpful immigrant-focused answer. Append businesses_text if provided.
    """
    if not client:
        return _fallback_response(language, knowledge_answer, businesses_text)

    if knowledge_answer:
        # Show full client answer; translate to user language only, no rewriting
        if translate_answer:
            reply = translate_verified_answer(knowledge_answer, language)
        else:
            reply = knowledge_answer
        if businesses_text:
            reply = reply + "\n\n" + businesses_text
        return reply

    lang_name = settings.LANGUAGE_NAMES.get(language, "English")
    system = f"""You are a helpful AI assistant for immigrant communities in the USA (Hispanic and Brazilian).
You provide accurate, verified information about living in the USA: immigration, housing, taxes, jobs, etc.
You MUST respond only in {lang_name}. Be concise and helpful."""

    user = f"""The user asked: {user_message}
Give a short helpful response in {lang_name} about living in the USA or suggest they ask more specifically. Respond only in {lang_name}."""

    try:
        resp = client.chat.completions.create(
            model=settings.GPT_MODEL,
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
    except Exception as e:
        logger.warning("GPT generate_response failed: %s", e)
        return _fallback_response(language, knowledge_answer, businesses_text)


def _fallback_response(language: str, knowledge_answer: str = None, businesses_text: str = None) -> str:
    if knowledge_answer:
        out = knowledge_answer
    else:
        out = "I'm here to help with questions about living in the USA and to connect you with local services. Please ask in English, Spanish, or Portuguese."
    if businesses_text:
        out = out + "\n\n" + businesses_text
    return out
