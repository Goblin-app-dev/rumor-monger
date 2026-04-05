"""
SQLAlchemy ORM models mapping to the Postgres schema.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.db import Base


class Source(Base):
    __tablename__ = "sources"

    id               = Column(Integer, primary_key=True)
    platform         = Column(String(20), nullable=False)
    handle           = Column(Text, nullable=False)
    url              = Column(Text)
    reputation_score = Column(Float, default=0.5)
    created_at       = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="source")

    __table_args__ = (
        UniqueConstraint("platform", "handle", name="uq_source_platform_handle"),
        CheckConstraint("platform IN ('reddit', 'youtube')", name="ck_source_platform"),
    )

    def __repr__(self):
        return f"<Source {self.platform}:{self.handle}>"


class Document(Base):
    __tablename__ = "documents"

    id            = Column(Integer, primary_key=True)
    source_id     = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"))
    document_type = Column(String(20), nullable=False)
    title         = Column(Text)
    url           = Column(Text)
    created_at    = Column(DateTime, default=datetime.utcnow)
    raw_text      = Column(Text)
    content_hash  = Column(String(64), unique=True)

    source   = relationship("Source", back_populates="documents")
    evidence = relationship("ClaimEvidence", back_populates="document")

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('post', 'comment', 'video', 'transcript')",
            name="ck_document_type",
        ),
    )

    def __repr__(self):
        return f"<Document {self.document_type} id={self.id}>"


class Claim(Base):
    __tablename__ = "claims"

    id            = Column(Integer, primary_key=True)
    text          = Column(Text, nullable=False, unique=True)
    edition       = Column(String(10), default="11th")
    faction       = Column(Text)
    unit_or_rule  = Column(Text)
    mechanic_type = Column(Text)
    status        = Column(String(20), default="unreviewed")
    created_at    = Column(DateTime, default=datetime.utcnow)

    evidence = relationship("ClaimEvidence", back_populates="claim")

    __table_args__ = (
        CheckConstraint(
            "status IN ('unreviewed','unsubstantiated','plausible','likely','confirmed','debunked')",
            name="ck_claim_status",
        ),
    )

    def __repr__(self):
        return f"<Claim id={self.id} status={self.status}>"


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id              = Column(Integer, primary_key=True)
    claim_id        = Column(Integer, ForeignKey("claims.id", ondelete="CASCADE"))
    document_id     = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    evidence_type   = Column(String(20), default="text")
    timestamp_start = Column(Text)
    timestamp_end   = Column(Text)
    created_at      = Column(DateTime, default=datetime.utcnow)

    claim    = relationship("Claim", back_populates="evidence")
    document = relationship("Document", back_populates="evidence")

    __table_args__ = (
        UniqueConstraint("claim_id", "document_id", name="uq_claim_evidence"),
        CheckConstraint(
            "evidence_type IN ('text', 'transcript')",
            name="ck_evidence_type",
        ),
    )

    def __repr__(self):
        return f"<ClaimEvidence claim={self.claim_id} doc={self.document_id}>"
