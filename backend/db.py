"""
SQLAlchemy engine, session factory, and declarative Base.

Engine is created lazily on first use so that st.secrets is fully
loaded before we try to read DATABASE_URL (critical for Streamlit Cloud).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
_SessionLocal = None


def _get_database_url() -> str:
    # 1. Streamlit secrets (Streamlit Cloud runtime)
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return url
    except Exception:
        pass
    # 2. Environment variable (GitHub Actions, local)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    # 3. Local dev default
    return "postgresql://warhammer:warhammer@localhost:5432/warhammer_leaks"


def _make_engine():
    url = _get_database_url()
    if "localhost" not in url and "127.0.0.1" not in url and "sslmode" not in url:
        url += "?sslmode=require"
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=5)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
