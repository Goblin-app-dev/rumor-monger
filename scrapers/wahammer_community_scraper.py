"""
Warhammer Community scraper – fetches official GW articles tagged #New40k
and related to 11th edition from warhammer-community.com.

All content from this source is marked status='confirmed' since it comes
directly from Games Workshop.
"""
import hashlib, logging, re, json, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime
from backend.db import SessionLocal
from backend.models import Source, Document, Claim, ClaimEvidence
from backend.config import CLAIM_KEYWORDS, FACTION_KEYWORDS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL  = "https://www.warhammer-community.com"
PLATFORM  = "warhammer_community"

# Pages to scrape for article listings
LISTING_PAGES = [
    "/en-gb/setting/warhammer-40000/",
    "/en-gb/all-news-and-features/",
]

# Keywords that mark an article as 11th-edition relevant.
# Deliberately tight — must explicitly reference 11th ed or the #New40k campaign.
EDITION_KEYWORDS = [
    "11th edition",
    "new40k",
    "#new40k",
    "new edition of warhammer 40",
    "new edition rules",
    "new rules for warhammer 40",
    "new apocalypse",
    "new defiler",          # confirmed 11th ed kit reveal
]

# Only ingest articles published on or after this date (11th ed announcement era)
EDITION_CUTOFF_YEAR = 2026

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}


def _sha256(t): return hashlib.sha256(t.encode()).hexdigest()


def _upsert_source(db) -> Source:
    """Single source entry for the whole Warhammer Community site."""
    src = db.query(Source).filter_by(platform=PLATFORM, handle="warhammer-community").first()
    if not src:
        src = Source(
            platform=PLATFORM,
            handle="warhammer-community",
            url=BASE_URL,
            reputation_score=1.0,   # Official GW source = maximum credibility
        )
        db.add(src)
        db.flush()
    return src


def _insert_doc(db, src, title, url, text, published_at=None) -> Document | None:
    h = _sha256(text)
    if db.query(Document).filter_by(content_hash=h).first():
        return None
    doc = Document(
        source_id=src.id,
        document_type="post",
        title=title,
        url=url,
        raw_text=text,
        content_hash=h,
        created_at=published_at or datetime.utcnow(),
    )
    db.add(doc)
    db.flush()
    return doc


def _is_relevant(title: str, text: str) -> bool:
    combined = (title + " " + text).lower()
    return any(kw in combined for kw in EDITION_KEYWORDS)


def _fetch_article_urls(session) -> list[str]:
    """Scrape listing pages for article hrefs."""
    seen = set()
    urls = []
    for page in LISTING_PAGES:
        try:
            r = session.get(BASE_URL + page, timeout=10)
            if r.status_code != 200:
                continue
            hrefs = re.findall(
                r'href=["\'](/en-gb/articles/[^"\'?#]+)["\']',
                r.text
            )
            for h in hrefs:
                if h not in seen:
                    seen.add(h)
                    urls.append(BASE_URL + h)
            log.info("Listing %s → %d articles", page, len(hrefs))
            time.sleep(0.3)
        except Exception as e:
            log.warning("Listing page %s: %s", page, e)
    return urls


def _parse_article(html: str) -> dict:
    """Extract title, description, body text, date from article HTML."""
    result = {"title": "", "description": "", "body": "", "date": None, "tags": []}

    # JSON-LD for structured metadata
    ld_blobs = re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    for blob in ld_blobs:
        try:
            d = json.loads(blob)
            if d.get("@type") == "Article":
                result["title"]       = d.get("headline", "")
                result["description"] = d.get("description", "")
                raw_date              = d.get("datePublished", "")
                if raw_date:
                    try:
                        result["date"] = datetime.fromisoformat(raw_date[:10])
                    except Exception:
                        pass
                kw = d.get("keywords", "")
                result["tags"] = [k.strip() for k in kw.split(",")] if kw else []
                break
        except Exception:
            continue

    # Body text: strip all HTML tags from <p> contents
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    clean = []
    for p in paras:
        text = re.sub(r'<[^>]+>', '', p).strip()
        if len(text) > 40:
            clean.append(text)
    result["body"] = "\n\n".join(clean)

    return result


def _detect_faction(s):
    lo = s.lower()
    for faction, kws in FACTION_KEYWORDS.items():
        for kw in kws:
            if kw in lo:
                return faction
    return None


def _detect_mechanic(s):
    from backend.config import CLAIM_KEYWORDS
    import re as _re
    MECHANICS = {
        "toughness": r"\btoughness\b",
        "strength":  r"\bstrength\b",
        "points":    r"\bpoints?\b",
        "detachment":r"\bdetachment\b",
        "stratagem": r"\bstratagem\b",
        "datasheet": r"\bdatasheet\b",
        "objective": r"\bobjective control\b",
        "save":      r"\bsave\b",
        "wounds":    r"\bwounds?\b",
        "attacks":   r"\battacks?\b",
    }
    lo = s.lower()
    for m, pat in MECHANICS.items():
        if _re.search(pat, lo):
            return m
    return None


def _split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    out = []
    for p in parts:
        out.extend(p.split("\n"))
    return [s.strip() for s in out if len(s.strip()) > 25]


def _upsert_confirmed_claim(db, sentence: str, doc: Document):
    """Insert or update a claim and force it to 'confirmed' status."""
    claim = db.query(Claim).filter_by(text=sentence).first()
    if not claim:
        claim = Claim(
            text=sentence,
            edition="11th",
            faction=_detect_faction(sentence),
            unit_or_rule=None,
            mechanic_type=_detect_mechanic(sentence),
            status="confirmed",   # Official GW source = confirmed
        )
        db.add(claim)
        db.flush()
    else:
        # Upgrade any existing claim from a rumour source to confirmed
        if claim.status not in ("confirmed", "debunked"):
            claim.status = "confirmed"

    # Link evidence (ON CONFLICT DO NOTHING)
    from sqlalchemy import text as sqltxt
    db.execute(
        sqltxt("""
            INSERT INTO claim_evidence (claim_id, document_id, evidence_type, created_at)
            VALUES (:cid, :did, 'text', NOW())
            ON CONFLICT (claim_id, document_id) DO NOTHING
        """),
        {"cid": claim.id, "did": doc.id}
    )


def run():
    db = SessionLocal()
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        src = _upsert_source(db)
        log.info("Warhammer Community source: id=%d reputation=%.1f", src.id, src.reputation_score)

        article_urls = _fetch_article_urls(session)
        log.info("Found %d article URLs across listing pages", len(article_urls))

        docs_new = claims_new = 0

        for url in article_urls:
            try:
                r = session.get(url, timeout=10)
                if r.status_code != 200:
                    continue

                parsed = _parse_article(r.text)
                title  = parsed["title"] or url.split("/")[-2].replace("-", " ").title()
                desc   = parsed["description"]
                body   = parsed["body"]
                full_text = f"{title}\n\n{desc}\n\n{body}".strip()

                # Skip articles not about 11th edition / #New40k
                if not _is_relevant(title, full_text):
                    continue

                # Skip articles published before the 11th edition era
                pub_date = parsed.get("date")
                if pub_date and pub_date.year < EDITION_CUTOFF_YEAR:
                    log.debug("Skipping pre-%d article: %s", EDITION_CUTOFF_YEAR, title[:60])
                    continue

                doc = _insert_doc(db, src, title, url, full_text, parsed.get("date"))
                if doc:
                    docs_new += 1
                    log.info("  + [%s] %s", parsed.get("date","?"), title[:70])

                    # Extract confirmed claims from article body
                    for sent in _split_sentences(full_text):
                        if any(kw in sent.lower() for kw in CLAIM_KEYWORDS):
                            _upsert_confirmed_claim(db, sent, doc)
                            claims_new += 1

                time.sleep(0.4)

            except Exception as e:
                log.warning("Article %s: %s", url, e)

        db.commit()
        log.info(
            "Warhammer Community: %d new articles, %d confirmed claims.",
            docs_new, claims_new
        )

    except Exception as e:
        db.rollback()
        log.error("WarCom scraper: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
