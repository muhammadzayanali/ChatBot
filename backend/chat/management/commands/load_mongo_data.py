"""
Load static/test data and client DOCX knowledge base into MongoDB (BraeloDB).
Stores data region-wise (by state). Run after MongoDB is running at localhost:27017.

  python manage.py load_mongo_data
  python manage.py load_mongo_data --translate   # translate answers to English
  python manage.py load_mongo_data --dry-run     # preview only
"""
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# Reuse DOCX parsing from load_docx
from chat.management.commands.load_docx import (
    QUESTIONS_FILE,
    RESPOSTAS_PREFIX,
    get_paragraphs,
    get_questions,
    parse_qa_pairs,
    parse_qa_q_first,
    parse_question_answer_multiparagraph,
    parse_question_answer_paragraphs,
    translate_to_english,
)

# All region/document_source DOCX files to load into knowledge_base (by region).
# Respostas <State>.docx -> state/region; Palavras chaves -> region "keywords".
RESPOSTAS_STATES = [
    "Arizona",
    "NY",
    "Texas",
    "Florida",
    "Colorado",
    "Illinois",
    "California",
    "Pennsylvania",
]
PALAVRAS_CHAVES_FILE = "Palavras chaves.docx"


# --- Seed data (same as seed_test_data) ---
TEST_USER_ID = "test-user"
TEST_STATE = "Arizona"
TEST_COUNTY = "Maricopa"
TEST_ZIP = "85001"
TEST_CITY = "Phoenix"
USER_LAT = 33.4484
USER_LON = -112.0740

SEED_BUSINESSES = [
    {
        "name": "Desert Legal Group",
        "category": "legal",
        "subcategory": "lawyer",
        "state": TEST_STATE,
        "city": TEST_CITY,
        "county": TEST_COUNTY,
        "zip_code": "85001",
        "latitude": 33.4490,
        "longitude": -112.0730,
        "languages": "en,es",
        "contact_info": "602-555-0100",
        "whatsapp_url": "https://wa.me/16025550100",
        "ad_package_name": "Premium",
        "impression_cap": 500,
        "impressions_used": 0,
        "rotation_index": 0,
        "is_active": True,
        "is_banned": False,
    },
    {
        "name": "Sun Valley Tax Services",
        "category": "tax",
        "subcategory": "tax_preparer",
        "state": TEST_STATE,
        "city": TEST_CITY,
        "county": TEST_COUNTY,
        "zip_code": "85002",
        "latitude": 33.4550,
        "longitude": -112.0680,
        "languages": "en,es,pt",
        "contact_info": "602-555-0200",
        "whatsapp_url": "https://wa.me/16025550200",
        "ad_package_name": None,
        "impression_cap": 1000,
        "impressions_used": 0,
        "rotation_index": 0,
        "is_active": True,
        "is_banned": False,
    },
    {
        "name": "Phoenix Immigration Help",
        "category": "immigration",
        "subcategory": "consultant",
        "state": TEST_STATE,
        "city": "Phoenix",
        "county": TEST_COUNTY,
        "zip_code": "85003",
        "latitude": 33.4460,
        "longitude": -112.0760,
        "languages": "en,es",
        "contact_info": "602-555-0300",
        "whatsapp_url": "",
        "ad_package_name": None,
        "impression_cap": 1000,
        "impressions_used": 0,
        "rotation_index": 0,
        "is_active": True,
        "is_banned": False,
    },
    {
        "name": "Maricopa Real Estate",
        "category": "housing",
        "subcategory": "real_estate_agent",
        "state": TEST_STATE,
        "city": TEST_CITY,
        "county": TEST_COUNTY,
        "zip_code": "85004",
        "latitude": 33.4520,
        "longitude": -112.0700,
        "languages": "en,es,pt",
        "contact_info": "602-555-0400",
        "whatsapp_url": "https://wa.me/16025550400",
        "ad_package_name": None,
        "impression_cap": 1000,
        "impressions_used": 0,
        "rotation_index": 0,
        "is_active": True,
        "is_banned": False,
    },
]


def seed_static_data(db, dry_run: bool):
    """Insert test user, ad package, and businesses into MongoDB."""
    now = datetime.utcnow()
    if dry_run:
        return
    users = db.users
    ad_packages = db.ad_packages
    businesses = db.businesses

    # Ad package
    ad_packages.delete_many({})
    ad_packages.insert_one({
        "name": "Premium",
        "priority": 10,
        "max_impressions": 500,
        "created_at": now,
    })
    # Test user
    users.delete_many({"external_id": TEST_USER_ID})
    users.insert_one({
        "external_id": TEST_USER_ID,
        "language_preference": "en",
        "state": TEST_STATE,
        "city": TEST_CITY,
        "county": TEST_COUNTY,
        "zip_code": TEST_ZIP,
        "location_enabled": True,
        "latitude": USER_LAT,
        "longitude": USER_LON,
        "created_at": now,
        "updated_at": now,
        "is_banned": False,
    })
    # Businesses
    businesses.delete_many({})
    for b in SEED_BUSINESSES:
        doc = {**b, "created_at": now}
        doc.pop("ad_package_name", None)
        ad_name = b.get("ad_package_name")
        if ad_name:
            doc["ad_package_name"] = ad_name  # reference by name
        businesses.insert_one(doc)


def _parse_qa_for_doc(paras: list, questions: list, filename: str):
    """
    Parse Q&A from paragraphs. Prefer Q-first format: when first word is Q, store text up to that as answer.
    Returns [(question, answer), ...] for this document.
    """
    if not paras:
        return []
    # 1) Q-first: paragraphs starting with "Q" are questions; text before each Q is the previous answer.
    pairs = parse_qa_q_first(paras)
    if pairs:
        return pairs
    # 2) If we have a questions list and same count, zip (e.g. Lista de Perguntas + state answers).
    if questions and len(paras) == len(questions):
        return list(zip(questions, paras))
    # 3) Fallbacks: P: / R:, question?, or multiparagraph.
    pairs = parse_qa_pairs(paras)
    if pairs:
        return pairs
    pairs = parse_question_answer_multiparagraph(paras)
    if pairs:
        return pairs
    pairs = parse_question_answer_paragraphs(paras)
    if pairs:
        return pairs
    return [(p, p) for p in paras]


def load_docx_into_mongo(db, translate: bool, dry_run: bool, command_stdout):
    """
    Load all region DOCX data into knowledge_base in MongoDB.
    Uses Q-first rule: when a statement starts with 'Q', text up to that is stored as the answer.
    Loads: Palavras chaves.docx (region=keywords) + Respostas Arizona, NY, Texas, Florida, Colorado, Illinois, California, Pennsylvania.
    """
    from chat.services.knowledge_service import get_embedding

    _backend_dir = Path(settings.BASE_DIR)
    candidates = [
        Path(settings.DOCX_DATA_DIR),
        _backend_dir.parent,
        _backend_dir,
        _backend_dir / "data",
        _backend_dir.parent / "documents",
    ]
    data_dir = None
    for d in candidates:
        if d.is_dir():
            if (d / QUESTIONS_FILE).exists() or (d / PALAVRAS_CHAVES_FILE).exists() or list(d.glob("Respostas *.docx")):
                data_dir = d
                break
    if data_dir is None:
        data_dir = _backend_dir.parent if _backend_dir.parent.is_dir() else _backend_dir

    command_stdout.write(f"Using data dir: {data_dir}")

    questions = []
    questions_file = data_dir / QUESTIONS_FILE
    if questions_file.exists():
        questions = get_questions(questions_file)
        command_stdout.write(f"Loaded {len(questions)} questions from {QUESTIONS_FILE}")

    # Build explicit file list: Palavras chaves + all Respostas by region.
    doc_sources = []
    # Palavras chaves -> region "keywords", document_source = filename
    if (data_dir / PALAVRAS_CHAVES_FILE).exists():
        doc_sources.append((data_dir / PALAVRAS_CHAVES_FILE, "keywords", PALAVRAS_CHAVES_FILE))
    for state in RESPOSTAS_STATES:
        path = data_dir / f"{RESPOSTAS_PREFIX}{state}.docx"
        if path.exists():
            doc_sources.append((path, state, f"Respostas {state}.docx"))

    if not doc_sources:
        command_stdout.write("No DOCX data found. Add Palavras chaves.docx and/or Respostas <State>.docx files.")
        return 0

    entries = []  # (region/state, question, answer, document_source)
    for path, region, document_source in doc_sources:
        paras = get_paragraphs(path)
        if not paras:
            command_stdout.write(f"  {document_source}: no paragraphs, skip")
            continue
        pairs = _parse_qa_for_doc(paras, questions if region != "keywords" else [], document_source)
        for q, a in pairs:
            if q and (a or q):
                entries.append((region, q, a or q, document_source))
        command_stdout.write(f"  {document_source}: {len(pairs)} Q&A (region={region})")

    if not entries:
        command_stdout.write("No Q&A entries parsed from DOCX files.")
        return 0

    if not settings.OPENAI_API_KEY:
        command_stdout.write("OPENAI_API_KEY not set. Embeddings will be empty; semantic search may be limited.")

    kb = db.knowledge_base
    if not dry_run:
        kb.delete_many({})

    added = 0
    for state, question, answer, document_source in entries:
        if translate:
            answer = translate_to_english(answer)
            if added == 0:
                command_stdout.write("Translating answers to English...")
        if dry_run:
            added += 1
            if added <= 3:
                command_stdout.write(f"  [dry-run] region={state}, doc={document_source}, q={question[:50]}...")
            continue
        emb = get_embedding(question)
        doc = {
            "state": state if state != "keywords" else None,
            "region": state,
            "county": None,
            "question": question,
            "answer": answer,
            "embedding": emb if emb else None,
            "document_source": document_source,
            "created_at": datetime.utcnow(),
        }
        kb.insert_one(doc)
        added += 1
        if added % 10 == 0:
            command_stdout.write(f"  Added {added}/{len(entries)}...")

    return added


class Command(BaseCommand):
    help = "Load static/test data and client DOCX knowledge base into MongoDB (BraeloDB), region-wise."

    def add_arguments(self, parser):
        parser.add_argument("--translate", action="store_true", help="Translate Spanish/Portuguese answers to English")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write to MongoDB")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        translate = options.get("translate", False)
        if dry_run:
            self.stdout.write("DRY RUN: no changes will be saved.")

        try:
            from chat.mongo_db import get_db, ensure_indexes
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"MongoDB connection failed: {e}"))
            self.stderr.write("Ensure MongoDB is running at localhost:27017 and pymongo is installed.")
            return

        db = get_db()
        ensure_indexes()

        self.stdout.write("Seeding static/test data (user, ad_package, businesses)...")
        seed_static_data(db, dry_run)
        if not dry_run:
            self.stdout.write(self.style.SUCCESS("  Inserted test user, Premium ad package, 4 businesses."))

        self.stdout.write("Loading DOCX knowledge base (region-wise)...")
        added = load_docx_into_mongo(db, translate, dry_run, self.stdout)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: would insert {added} knowledge_base docs."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Inserted {added} knowledge_base docs (region-wise)."))
        self.stdout.write("Database: BraeloDB. Use USE_MONGO=true so the app reads from MongoDB.")
