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


def _sanitize(text: str) -> str:
    """Remove characters that can break prompts or JSON strings."""
    return (text
            .replace('\\', ' ')
            .replace('"', ' ')
            .replace("'", ' ')
            .replace('\u2018', ' ')   # left single quote
            .replace('\u2019', ' ')   # right single quote
            .replace('\u201c', ' ')   # left double quote
            .replace('\u201d', ' ')   # right double quote
            .replace('\n', ' ')
            .replace('\r', ' ')
            .strip())


def _build_prompt(claim: Claim, evidence_texts: list[str], source_handles: list[str]) -> str:
    evidence_block = "\n\n".join(
        f"Source {i+1} ({source_handles[i] if i < len(source_handles) else 'unknown'}): {_sanitize(t)[:500]}"
        for i, t in enumerate(evidence_texts[:3])
    )
    source_list = ", ".join(source_handles[:3]) if source_handles else "unknown"

    return f"""You are an expert Warhammer 40,000 analyst tracking what is NEW or CHANGED in 11th edition compared to 10th edition.

Your job is to extract the SPECIFIC CONTENT from this source — what rules changed, what models are new, what mechanics are different, what points costs shifted.

Do NOT write generic summaries like "analyst expresses excitement" or "source discusses 11th edition".
Do NOT summarize feelings or opinions — only summarize factual claims about rules, models, mechanics, or points.

SOURCE(S): {source_list}
SOURCE TYPE: {claim.status} ({'Official GW announcement' if claim.status == 'confirmed' else 'Community leak/rumour'})

RAW EXTRACTED TEXT:
{_sanitize(claim.text)}

FULL SOURCE CONTEXT:
{evidence_block if evidence_block else 'No additional context available.'}

Instructions:
1. ai_title: Format as "[Source Name] discusses [specific topic(s)]" — e.g. "Auspex Tactics discusses Intercessor toughness buff and free weapons". List the actual topics, not vague descriptions. Max 15 words.
2. ai_summary: 2-4 sentences covering ONLY the specific 11th edition changes/reveals mentioned: what rule/model/mechanic changed, how it differs from 10th edition, and what it means for gameplay. Be specific — name units, stats, rules.
3. ai_confidence: 1-2 sentences on source credibility — is this GW official, a known leaker, a community rumour? How many sources corroborate it?
4. ai_faction: The specific Warhammer 40k faction (e.g. 'Space Marines', 'Necrons', 'Orks') or 'All Factions' if it applies broadly.

Return only the JSON object."""


# JSON schema for strict structured output
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "ai_title":      {"type": "string", "description": "Source name + specific topics discussed, max 15 words"},
        "ai_summary":    {"type": "string", "description": "2-4 sentences about specific rules/models/mechanics changed in 11th edition"},
        "ai_confidence": {"type": "string", "description": "1-2 sentences on source credibility"},
        "ai_faction":    {"type": "string", "description": "Specific faction name or All Factions"},
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
        # Re-summarize ALL claims so new prompt is applied everywhere
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
            # Gather evidence texts AND source handles for context
            evidence_rows = db.query(ClaimEvidence).filter(
                ClaimEvidence.claim_id == claim.id
            ).all()
            evidence_texts = []
            source_handles = []
            for ev in evidence_rows:
                doc = db.query(Document).filter_by(id=ev.document_id).first()
                if doc and doc.raw_text:
                    evidence_texts.append(doc.raw_text[:500])
                    src = db.query(Source).filter_by(id=doc.source_id).first()
                    if src:
                        source_handles.append(src.handle)

            # Skip claims that are too short or lack substantive content
            if len(claim.text.strip()) < 40:
                claim.summarized_at = datetime.now(timezone.utc)  # mark done, skip
                db.flush()
                continue

            try:
                prompt = _build_prompt(claim, evidence_texts, source_handles)
                result = _call_gemini(prompt, api_key)

                claim.ai_title      = result.get("ai_title", "")[:200]
                claim.ai_summary    = result.get("ai_summary", "")[:1000]
                claim.ai_confidence = result.get("ai_confidence", "")[:500]
                claim.ai_faction    = result.get("ai_faction", "")[:100]
                claim.summarized_at = datetime.now(timezone.utc)

                db.flush()
                success += 1
                log.info("  ✓ [%d] %s", claim.id, claim.ai_title[:70])

                # Stay under free tier rate limit
                time.sleep(8)

            except Exception as e:
                log.warning("  ✗ [%d] Gemini error: %s — marking for retry", claim.id, e)
                # Don't mark as summarized — will retry next run
                time.sleep(3)

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
