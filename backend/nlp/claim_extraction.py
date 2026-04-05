"""
NLP Claim Extractor – sentences containing WH40k rule-change keywords become claims.
Evidence links use INSERT ... ON CONFLICT DO NOTHING to avoid duplicate violations.
"""
import logging, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.config import CLAIM_KEYWORDS, FACTION_KEYWORDS
from backend.db import SessionLocal
from backend.models import Document, Claim, ClaimEvidence

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MECHANIC_PATTERNS = {
    "toughness":      r"\btoughness\b",
    "strength":       r"\bstrength\b",
    "points":         r"\bpoints?\b",
    "detachment":     r"\bdetachment\b",
    "stratagem":      r"\bstratagem\b",
    "datasheet":      r"\bdatasheet\b",
    "objective":      r"\bobjective control\b",
    "save":           r"\bsave\b",
    "wounds":         r"\bwounds?\b",
    "attacks":        r"\battacks?\b",
    "leadership":     r"\bleadership\b",
    "weapon_profile": r"\b(weapon skill|ballistic skill|ap |damage)\b",
}


def _sentences(text):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    out = []
    for p in parts:
        out.extend(p.split("\n"))
    return [s.strip() for s in out if len(s.strip()) > 25]


def _faction(s):
    lo = s.lower()
    for faction, kws in FACTION_KEYWORDS.items():
        for kw in kws:
            if kw in lo:
                return faction
    return None


def _mechanic(s):
    lo = s.lower()
    for m, pat in MECHANIC_PATTERNS.items():
        if re.search(pat, lo):
            return m
    return None


def _unit(s):
    m = re.findall(r'(?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+', s)
    return m[0].strip() if m else None


def _is_claim(s):
    lo = s.lower()
    return any(kw in lo for kw in CLAIM_KEYWORDS)


def run():
    db = SessionLocal()
    try:
        docs = db.query(Document).all()
        log.info("Processing %d documents …", len(docs))
        claims_new = ev_new = 0

        for doc in docs:
            if not doc.raw_text:
                continue
            ev_type = "transcript" if doc.document_type == "transcript" else "text"

            for sent in _sentences(doc.raw_text):
                if not _is_claim(sent):
                    continue
                if len(sent) < 30 or len(sent) > 800:
                    continue

                # Upsert claim
                claim = db.query(Claim).filter_by(text=sent).first()
                if not claim:
                    claim = Claim(
                        text=sent, edition="11th",
                        faction=_faction(sent),
                        unit_or_rule=_unit(sent),
                        mechanic_type=_mechanic(sent),
                        status="unreviewed",
                    )
                    db.add(claim)
                    db.flush()
                    claims_new += 1

                # Insert evidence with ON CONFLICT DO NOTHING
                db.execute(
                    text("""
                        INSERT INTO claim_evidence (claim_id, document_id, evidence_type, created_at)
                        VALUES (:cid, :did, :et, NOW())
                        ON CONFLICT (claim_id, document_id) DO NOTHING
                    """),
                    {"cid": claim.id, "did": doc.id, "et": ev_type}
                )
                ev_new += 1

        db.commit()
        log.info("Done: %d new claims, %d evidence links.", claims_new, ev_new)
    except Exception as e:
        db.rollback()
        log.error("Claim extraction: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
