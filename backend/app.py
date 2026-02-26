# Braelo Flask app: LLM-based chat + optional legacy intent fallback
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import OPENAI_API_KEY
from database.models import init_db

# Initialize DB
init_db()

app = Flask(__name__)
CORS(app)

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
        if os.path.isfile("chatbot_model.h5") and os.path.isfile("intents.json") and os.path.isfile("words.pkl") and os.path.isfile("classes.pkl"):
            _legacy_model = load_model("chatbot_model.h5")
            _legacy_intents = json.load(open("intents.json", encoding="utf-8"))
            _legacy_words = pickle.load(open("words.pkl", "rb"))
            _legacy_classes = pickle.load(open("classes.pkl", "rb"))
            return True
    except Exception:
        pass
    return False


@app.route("/")
def home():
    try:
        from flask import render_template
        return render_template("index.html")
    except Exception:
        pass
    return "<p>Braelo API. Use POST /api/chat or /get</p>"


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return "", 204
    try:
        data = request.get_json(force=True, silent=True) or {}
        message = (data.get("message") or data.get("msg") or "").strip()
        if not message or len(message) > 4000:
            return jsonify({"error": "Invalid or missing message", "response": ""}), 400
        user_id = data.get("user_id") or data.get("session_id") or request.remote_addr
        session_id = data.get("session_id") or user_id
    except Exception:
        return jsonify({"error": "Bad request", "response": ""}), 400

    try:
        from chat_flow import process_message
        out = process_message(message, user_id=user_id, session_id=session_id)
        return jsonify({
            "response": out["response"],
            "detected_language": out.get("detected_language", "en"),
            "businesses": out.get("businesses", []),
            "intent": out.get("intent", ""),
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "response": "Sorry, something went wrong. Please try again.",
            "detected_language": "en",
            "businesses": [],
        }), 500


@app.route("/get", methods=["POST", "OPTIONS"])
def get():
    """Legacy form endpoint: msg in form or JSON. Uses LLM flow if OPENAI_API_KEY set, else legacy model."""
    if request.method == "OPTIONS":
        return "", 204
    msg = request.form.get("msg") or (request.get_json(silent=True) or {}).get("msg") or ""
    msg = (msg or "").strip()
    if not msg:
        return "Please send a message.", 400

    if OPENAI_API_KEY:
        try:
            from chat_flow import process_message
            out = process_message(msg, user_id=request.remote_addr, session_id=request.remote_addr)
            return out["response"]
        except Exception:
            return "Sorry, something went wrong. Please try again."

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
        return res

    return "Chat is not configured. Set OPENAI_API_KEY or add chatbot_model.h5 and intents.json."


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "llm": bool(OPENAI_API_KEY)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
