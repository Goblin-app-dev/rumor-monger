"""
SQLAlchemy engine, session factory, and declarative Base.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL

# Supabase (and most hosted Postgres) requires SSL.
# Add sslmode=require if not already present in the URL.
_db_url = DATABASE_URL
if _db_url and "sslmode" not in _db_url and "supabase" in _db_url:
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
