"""
AI Summarizer – uses Google Gemini (free tier) to turn raw extracted claim
sentences into clean, human-readable summaries.

For each unsummarized claim it produces:
  - ai_title:      short headline (≤10 words)
  - ai_summary:    2-3 sentence plain-English explanation
  - ai_confidence: plain-English explanation of why this claim is credible or not
  - ai_faction:    corrected/confirmed faction tag

Requires: GEMINI_API_KEY environment variable or Streamlit secret.
Get a free key at: https://aistudio.google.com
"""
import logging, os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from datetime import datetime, timezone
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _get_api_key() -> str:
    # Try Streamlit secrets first
    try:
        import streamlit as st
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def _build_prompt(claim: Claim, evidence_texts: list[str]) -> str:
    evidence_block = "\n\n".join(
        f"Source {i+1}: {t[:400]}" for i, t in enumerate(evidence_texts[:3])
    )
    return f"""You are an analyst tracking Warhammer 40,000 11th edition leaks and rumours.

Below is a raw claim extracted from Reddit posts and YouTube videos, followed by the source texts it came from.

RAW CLAIM:
{claim.text}

SOURCE EVIDENCE:
{evidence_block if evidence_block else "No additional source context available."}

Current status: {claim.status}
Detected mechanic: {claim.mechanic_type or "unknown"}
Detected faction: {claim.faction or "unknown"}

Produce a JSON response with exactly these fields:
{{
  "ai_title": "Short headline under 10 words describing this rumour",
  "ai_summary": "2-3 sentences explaining what this rumour claims in plain English, what it would mean for the game if true, and any context from the sources.",
  "ai_confidence": "1-2 sentences explaining why this claim is credible or not, based on the source quality, number of sources, and consistency.",
  "ai_faction": "The Warhammer 40k faction this applies to, or 'All Factions' if general, or 'Unknown'"
}}

Return ONLY valid JSON, no markdown, no extra text."""


# JSON schema for strict structured output
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "ai_title":      {"type": "string"},
        "ai_summary":    {"type": "string"},
        "ai_confidence": {"type": "string"},
        "ai_faction":    {"type": "string"},
    },
    "required": ["ai_title", "ai_summary", "ai_confidence", "ai_faction"]
}


def _call_gemini(prompt: str, api_key: str) -> dict:
    resp = requests.post(
        f"{GEMINI_API_URL}?key={api_key}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            }
        },
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return json.loads(text)


def run(batch_size: int = 50):
    api_key = _get_api_key()
    if not api_key:
        log.warning("GEMINI_API_KEY not set — skipping AI summarization.")
        log.warning("Get a free key at https://aistudio.google.com and add it as GEMINI_API_KEY secret.")
        return

    db = SessionLocal()
    try:
        # Only process claims that haven't been summarized yet
        unsummarized = (
            db.query(Claim)
            .filter(Claim.summarized_at.is_(None))
            .order_by(Claim.id.desc())
            .limit(batch_size)
            .all()
        )
        log.info("Summarizing %d claims with Gemini …", len(unsummarized))

        success = 0
        for claim in unsummarized:
            # Gather evidence texts for context
            evidence_rows = db.query(ClaimEvidence).filter(
                ClaimEvidence.claim_id == claim.id
            ).all()
            evidence_texts = []
            for ev in evidence_rows:
                doc = db.query(Document).filter_by(id=ev.document_id).first()
                if doc and doc.raw_text:
                    evidence_texts.append(doc.raw_text[:500])

            try:
                prompt = _build_prompt(claim, evidence_texts)
                result = _call_gemini(prompt, api_key)

                claim.ai_title      = result.get("ai_title", "")[:200]
                claim.ai_summary    = result.get("ai_summary", "")[:1000]
                claim.ai_confidence = result.get("ai_confidence", "")[:500]
                claim.ai_faction    = result.get("ai_faction", "")[:100]
                claim.summarized_at = datetime.now(timezone.utc)

                db.flush()
                success += 1
                log.info("  ✓ [%d] %s", claim.id, claim.ai_title[:60])

                # Free tier: stay well under 15 req/min
                time.sleep(8)

            except Exception as e:
                log.warning("  ✗ [%d] Gemini error: %s", claim.id, e)
                time.sleep(2)

        db.commit()
        log.info("Summarization complete: %d/%d claims processed.", success, len(unsummarized))

    except Exception as e:
        db.rollback()
        log.error("Summarizer error: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
