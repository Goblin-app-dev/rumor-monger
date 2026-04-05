-- Warhammer 40k 11th Edition Leak Intelligence System
-- Initial Schema Migration

CREATE TABLE IF NOT EXISTS sources (
    id          SERIAL PRIMARY KEY,
    platform    VARCHAR(20) NOT NULL CHECK (platform IN ('reddit', 'youtube', 'warhammer_community')),
    handle      TEXT NOT NULL,
    url         TEXT,
    reputation_score FLOAT DEFAULT 0.5,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (platform, handle)
);

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    source_id       INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    document_type   VARCHAR(20) NOT NULL CHECK (document_type IN ('post', 'comment', 'video', 'transcript')),
    title           TEXT,
    url             TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    raw_text        TEXT,
    content_hash    VARCHAR(64),
    UNIQUE (content_hash)
);

CREATE TABLE IF NOT EXISTS claims (
    id              SERIAL PRIMARY KEY,
    text            TEXT NOT NULL,
    edition         VARCHAR(10) DEFAULT '11th',
    faction         TEXT,
    unit_or_rule    TEXT,
    mechanic_type   TEXT,
    status          VARCHAR(20) DEFAULT 'unreviewed'
                        CHECK (status IN ('unreviewed','unsubstantiated','plausible','likely','confirmed','debunked')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (text)
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    id              SERIAL PRIMARY KEY,
    claim_id        INTEGER REFERENCES claims(id) ON DELETE CASCADE,
    document_id     INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    evidence_type   VARCHAR(20) DEFAULT 'text' CHECK (evidence_type IN ('text', 'transcript')),
    timestamp_start TEXT,
    timestamp_end   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (claim_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON claim_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_document_id ON claim_evidence(document_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
