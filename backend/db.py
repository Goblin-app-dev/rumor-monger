"""
SQLAlchemy engine, session factory, and declarative Base.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL

# Hosted Postgres (Supabase, Railway, Render, etc.) requires SSL.
# Add sslmode=require whenever the DB is not localhost and no sslmode is set.
_db_url = DATABASE_URL
if _db_url and "sslmode" not in _db_url and "localhost" not in _db_url and "127.0.0.1" not in _db_url:
    _db_url += "?sslmode=require"

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=5,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db():
    """Yield a database session and close it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
