"""
Match user messages against intents.json for casual conversation (greetings, goodbye, thanks, etc.).
Returns a predefined response so we don't hit knowledge base or GPT for small talk.
"""
import json
import re
from pathlib import Path

# Casual tags we handle with intents.json (not knowledge base)
CASUAL_TAGS = frozenset({
    "greetings", "goodbye", "thanks", "name1", "name", "fav", "need", "do",
    "noanswer", "date", "AI", "sentiment", "sapient", "abbr", "lang", "sound",
    "artificial", "imortal", "sense", "clone", "move",
})

_INTENTS_CACHE = None


def _normalize(text: str) -> str:
    if not text:
        return ""
    return text.lower().strip()


def _load_intents() -> list:
    global _INTENTS_CACHE
    if _INTENTS_CACHE is not None:
        return _INTENTS_CACHE
    backend_dir = Path(__file__).resolve().parent.parent
    path = backend_dir / "intents.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _INTENTS_CACHE = data.get("intents", [])
        return _INTENTS_CACHE
    except Exception:
        _INTENTS_CACHE = []
        return []


def _matches_pattern(message_norm: str, pattern: str) -> bool:
    """True if message matches this pattern (contains, equals, or is contained)."""
    if not pattern or not message_norm:
        return False
    p = _normalize(pattern)
    if not p:
        return False
    return (
        p == message_norm
        or p in message_norm
        or message_norm in p
        or message_norm.startswith(p)
        or p.startswith(message_norm)
    )


def _extract_name(message: str) -> str:
    """Extract name from 'my name is X', 'I'm X', 'I am X'."""
    msg = message.strip()
    for prefix in ("my name is", "i'm", "i am", "me chamo", "me llamo", "mi nombre es"):
        if msg.lower().startswith(prefix):
            name = msg[len(prefix):].strip(" ,.")
            if name:
                return name
    return ""


def get_casual_response(message: str) -> tuple:
    """
    If message matches a casual intent, return (response_text, tag).
    Otherwise return (None, None).
    For 'name' intent, {n} in response is replaced with extracted name.
    """
    if not message or not message.strip():
        return None, None
    message_norm = _normalize(message)
    intents = _load_intents()
    for intent in intents:
        tag = intent.get("tag", "")
        if tag not in CASUAL_TAGS:
            continue
        patterns = intent.get("patterns") or []
        for pattern in patterns:
            if not pattern and tag != "noanswer":
                continue
            if _matches_pattern(message_norm, pattern):
                responses = intent.get("responses") or []
                if not responses:
                    continue
                import random
                response = random.choice(responses)
                if tag == "name":
                    name = _extract_name(message)
                    response = response.replace("{n}", name if name else "there")
                return response.strip(), tag
    return None, None
