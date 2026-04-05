"""
Veracity Engine – scores each claim based on evidence count and source diversity,
then updates the claim status.
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _compute_status(evidence_count: int, source_count: int,
                    has_transcript: bool, avg_reputation: float) -> str:
    """
    Scoring rubric:
      - 0 evidence                          → unsubstantiated
      - 1 evidence, low reputation          → unsubstantiated
      - 1 evidence, decent reputation       → plausible
      - 2 evidence OR transcript evidence   → plausible
      - 3+ evidence, 2+ sources             → likely
      - 5+ evidence, 3+ sources             → confirmed (provisional)
    """
    if evidence_count == 0:
        return "unsubstantiated"
    if evidence_count == 1:
        if avg_reputation >= 0.6:
            return "plausible"
        return "unsubstantiated"
    if evidence_count == 2 or has_transcript:
        return "plausible"
    if evidence_count >= 3 and source_count >= 2:
        return "likely"
    if evidence_count >= 5 and source_count >= 3:
        return "confirmed"
    return "plausible"


def run():
    db = SessionLocal()
    try:
        claims = db.query(Claim).all()
        log.info("Scoring %d claims …", len(claims))

        updated = 0
        for claim in claims:
            evidence_rows = (
                db.query(ClaimEvidence)
                .filter(ClaimEvidence.claim_id == claim.id)
                .all()
            )

            evidence_count = len(evidence_rows)
            has_transcript = any(e.evidence_type == "transcript" for e in evidence_rows)

            # Gather unique sources and their reputations
            source_ids = set()
            reputations = []
            for ev in evidence_rows:
                doc = db.query(Document).filter_by(id=ev.document_id).first()
                if doc and doc.source_id:
                    source_ids.add(doc.source_id)
                    src = db.query(Source).filter_by(id=doc.source_id).first()
                    if src:
                        reputations.append(src.reputation_score or 0.5)

            source_count = len(source_ids)
            avg_reputation = sum(reputations) / len(reputations) if reputations else 0.5

            new_status = _compute_status(
                evidence_count, source_count, has_transcript, avg_reputation
            )

            if claim.status != new_status:
                claim.status = new_status
                updated += 1

        db.commit()
        log.info("Veracity engine updated %d claim statuses.", updated)
    except Exception as e:
        db.rollback()
        log.error("Veracity engine error: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
