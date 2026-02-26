"""
SQLAlchemy models for Braelo: users, chat_history, knowledge_base, businesses, impressions, leads.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(128), unique=True, nullable=False, index=True)  # e.g. phone/wa_id or session
    language_preference = Column(String(8), default="en")
    state = Column(String(64), nullable=True)
    city = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    external_id = Column(String(128), nullable=True, index=True)  # when user not yet in DB
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    entities_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(64), nullable=True)  # Arizona, Texas, etc. or null for general
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)  # JSON array of floats from OpenAI embedding
    created_at = Column(DateTime, default=datetime.utcnow)


class AdPackage(Base):
    __tablename__ = "ad_packages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    priority = Column(Integer, default=0)  # higher = shown first
    max_impressions = Column(Integer, default=1000)


class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    category = Column(String(128), nullable=True)
    subcategory = Column(String(128), nullable=True)
    state = Column(String(64), nullable=True)
    city = Column(String(128), nullable=True)
    languages = Column(String(256), nullable=True)  # comma-separated: en,es,pt
    contact_info = Column(Text, nullable=True)  # phone, email, link
    ad_package_id = Column(Integer, ForeignKey("ad_packages.id"), nullable=True)
    impression_cap = Column(Integer, default=1000)
    impressions_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ImpressionsLog(Base):
    __tablename__ = "impressions_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    external_id = Column(String(128), nullable=True)
    session_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    external_id = Column(String(128), nullable=True)
    action_type = Column(String(32), default="click")
    created_at = Column(DateTime, default=datetime.utcnow)
