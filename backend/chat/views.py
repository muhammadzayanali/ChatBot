"""
Django views for Braelo chatbot API.
Ported from Flask app.py — same endpoints, same JSON format.
"""
import os
import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings as django_settings

# Optional legacy chatbot (only if OPENAI_API_KEY not set and files exist)
_legacy_model = None
_legacy_intents = None
_legacy_words = None
_legacy_classes = None


def _load_legacy():
    global _legacy_model, _legacy_intents, _legacy_words, _legacy_classes
    if _legacy_model is not None:
        return True
    try:
        import pickle
        from keras.models import load_model
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base, "chatbot_model.h5")
        intents_path = os.path.join(base, "intents.json")
        words_path = os.path.join(base, "words.pkl")
        classes_path = os.path.join(base, "classes.pkl")
        if all(os.path.isfile(f) for f in [model_path, intents_path, words_path, classes_path]):
            _legacy_model = load_model(model_path)
            _legacy_intents = json.load(open(intents_path, encoding="utf-8"))
            _legacy_words = pickle.load(open(words_path, "rb"))
            _legacy_classes = pickle.load(open(classes_path, "rb"))
            return True
    except Exception:
        pass
    return False


def home(request):
    """Render the legacy chat template, or show a simple message."""
    try:
        return render(request, "chat/index.html")
    except Exception:
        return HttpResponse("<p>Braelo API. Use POST /api/chat or /get</p>")


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_chat(request):
    """Main chat API endpoint — same as Flask /api/chat."""
    if request.method == "OPTIONS":
        return HttpResponse("", status=200)

    try:
        data = json.loads(request.body) if request.body else {}
        message = (data.get("message") or data.get("msg") or "").strip()
        if not message or len(message) > 4000:
            return JsonResponse({"error": "Invalid or missing message", "response": ""}, status=400)
        user_id = data.get("user_id") or data.get("session_id") or _get_client_ip(request)
        session_id = data.get("session_id") or user_id
    except Exception:
        return JsonResponse({"error": "Bad request", "response": ""}, status=400)

    try:
        from chat.chat_flow import process_message
        out = process_message(message, user_id=user_id, session_id=session_id)
        return JsonResponse({
            "response": out["response"],
            "detected_language": out.get("detected_language", "en"),
            "businesses": out.get("businesses", []),
            "intent": out.get("intent", ""),
        })
    except Exception as e:
        return JsonResponse({
            "error": str(e),
            "response": "Sorry, something went wrong. Please try again.",
            "detected_language": "en",
            "businesses": [],
        }, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def legacy_get(request):
    """Legacy form endpoint: msg in form or JSON. Same as Flask /get."""
    if request.method == "OPTIONS":
        return HttpResponse("", status=200)

    # Try form data first, then JSON
    msg = request.POST.get("msg") or ""
    if not msg:
        try:
            data = json.loads(request.body) if request.body else {}
            msg = data.get("msg") or ""
        except Exception:
            msg = ""
    msg = msg.strip()

    if not msg:
        return HttpResponse("Please send a message.", status=400)

    if django_settings.OPENAI_API_KEY:
        try:
            from chat.chat_flow import process_message
            out = process_message(msg, user_id=_get_client_ip(request), session_id=_get_client_ip(request))
            return HttpResponse(out["response"])
        except Exception:
            return HttpResponse("Sorry, something went wrong. Please try again.")

    if _load_legacy():
        import random
        import numpy as np
        import nltk
        from nltk.stem import WordNetLemmatizer
        lemmatizer = WordNetLemmatizer()

        def clean_up_sentence(sentence):
            sentence_words = nltk.word_tokenize(sentence)
            return [lemmatizer.lemmatize(w.lower()) for w in sentence_words]

        def bow(sentence):
            sentence_words = clean_up_sentence(sentence)
            bag = [0] * len(_legacy_words)
            for s in sentence_words:
                for i, w in enumerate(_legacy_words):
                    if w == s:
                        bag[i] = 1
            return np.array(bag)

        def predict_class(sentence):
            p = bow(sentence)
            res = _legacy_model.predict(np.array([p]))[0]
            thresh = 0.25
            results = [[i, r] for i, r in enumerate(res) if r > thresh]
            results.sort(key=lambda x: x[1], reverse=True)
            return [{"intent": _legacy_classes[r[0]], "probability": str(r[1])} for r in results]

        def get_response(ints):
            tag = ints[0]["intent"]
            for i in _legacy_intents["intents"]:
                if i["tag"] == tag:
                    return random.choice(i["responses"])
            return "Sorry, I didn't understand that."

        if msg.startswith("my name is"):
            name = msg[11:]
            ints = predict_class(msg)
            res = get_response(ints).replace("{n}", name)
        elif msg.startswith("hi my name is"):
            name = msg[14:]
            ints = predict_class(msg)
            res = get_response(ints).replace("{n}", name)
        else:
            ints = predict_class(msg)
            res = get_response(ints) if ints else "Sorry, I didn't understand that."
        return HttpResponse(res)

    return HttpResponse("Chat is not configured. Set OPENAI_API_KEY or add chatbot_model.h5 and intents.json.")


@require_http_methods(["GET"])
def health(request):
    """Health check endpoint — same as Flask /api/health."""
    return JsonResponse({"status": "ok", "llm": bool(django_settings.OPENAI_API_KEY)})


@require_http_methods(["GET"])
def debug_knowledge(request):
    """Debug knowledge base — same as Flask /api/debug/knowledge."""
    from chat.models import KnowledgeBase
    total = KnowledgeBase.objects.count()
    with_emb = KnowledgeBase.objects.filter(embedding_json__isnull=False).count()
    sample = KnowledgeBase.objects.all()[:5]
    return JsonResponse({
        "knowledge_base_total": total,
        "knowledge_base_with_embeddings": with_emb,
        "sample_questions": [
            {
                "q": r.question[:80] + ("..." if len(r.question or "") > 80 else ""),
                "state": r.state,
            }
            for r in sample
        ],
        "openai_key_set": bool(django_settings.OPENAI_API_KEY),
    })


def _get_client_ip(request):
    """Get client IP from request (for user identification)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
