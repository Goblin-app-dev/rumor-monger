"""
Reddit scraper – Arctic Shift public API (no key required).
Scoped tightly to stay under 30s total runtime.
Falls back to PRAW (if keys set) or mock data.
"""
import hashlib, logging, sys, os, time, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backend.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from backend.db import SessionLocal
from backend.models import Source, Document

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ARCTIC = "https://arctic-shift.photon-reddit.com/api"

# Tight scope – only queries with confirmed results, only 2 subreddits
SEARCHES = [
    ("Warhammer40k",         "11th edition leak"),
    ("Warhammer40k",         "11th edition rules"),
    ("Warhammer40k",         "11th edition rumour"),
    ("WarhammerCompetitive", "11th edition rules"),
    ("WarhammerCompetitive", "11th edition new edition"),
]

MOCK_POSTS = [
    {"author": "LeakHunter42",    "subreddit": "Warhammer40k",
     "title": "11th edition – Space Marines toughness changes",
     "url": "https://reddit.com/r/Warhammer40k/mock1",
     "text": "Space Marines will have toughness 5 on Intercessors in 11th edition. "
             "Detachment rules are overhauled – unique army rule per faction. "
             "Points reduced ~10-15%. Bolt rifle strength going up to 5."},
    {"author": "TournamentPro99", "subreddit": "WarhammerCompetitive",
     "title": "11th ed – detachment and stratagem changes",
     "url": "https://reddit.com/r/WarhammerCompetitive/mock2",
     "text": "Stratagems capped at 2 per phase in 11th edition. "
             "Objective control for monsters and vehicles goes to 3 OC default. "
             "Datasheet abilities replace faction-wide stratagems."},
    {"author": "NecronFan2026",   "subreddit": "Warhammer40k",
     "title": "Necron 11th edition leaks – dynasty rules",
     "url": "https://reddit.com/r/Warhammer40k/mock3",
     "text": "Necron Warriors getting toughness 5 in 11th edition. "
             "Reanimation Protocols triggers end of opponent's shooting phase. "
             "Points for Warriors dropping to 15 each."},
    {"author": "AlphaLeak",       "subreddit": "Warhammer40k",
     "title": "Big 11th edition leak – multiple factions",
     "url": "https://reddit.com/r/Warhammer40k/mock4",
     "text": "Weapons are now free and included in unit points cost in 11th edition. "
             "T'au getting new detachment for Greater Good ability sharing. "
             "Chaos Space Marines get new army rule tied to mark of chaos."},
]


def _sha256(t): return hashlib.sha256(t.encode()).hexdigest()

def _upsert_source(db, handle, url):
    s = db.query(Source).filter_by(platform="reddit", handle=handle).first()
    if not s:
        s = Source(platform="reddit", handle=handle, url=url, reputation_score=0.5)
        db.add(s); db.flush()
    return s

def _insert_doc(db, src, dtype, title, url, text):
    h = _sha256(text)
    if db.query(Document).filter_by(content_hash=h).first():
        return False
    db.add(Document(source_id=src.id, document_type=dtype, title=title,
                    url=url, raw_text=text, content_hash=h, created_at=datetime.utcnow()))
    db.flush()
    return True


def _scrape_arctic_shift(db):
    sess = requests.Session()
    sess.headers["User-Agent"] = "warhammer-leak-intel/1.0"
    count = 0
    for sub, query in SEARCHES:
        try:
            r = sess.get(f"{ARCTIC}/posts/search",
                         params={"subreddit": sub, "query": query,
                                 "limit": 15, "sort": "desc"},
                         timeout=8)
            if r.status_code != 200:
                continue
            posts = r.json().get("data", [])
            log.info("r/%s '%s' → %d posts", sub, query, len(posts))
            for p in posts:
                author = p.get("author") or "deleted"
                title  = p.get("title", "")
                body   = (p.get("selftext") or "").strip()
                url    = p.get("url") or f"https://reddit.com{p.get('permalink','')}"
                text   = f"{title}\n\n{body}".strip()
                if len(text) < 30:
                    continue
                src = _upsert_source(db, author, f"https://reddit.com/user/{author}")
                if _insert_doc(db, src, "post", title, url, text):
                    count += 1
            time.sleep(0.2)
        except Exception as e:
            log.warning("Arctic Shift r/%s '%s': %s", sub, query, e)
    return count


def _scrape_praw(db):
    import praw
    reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                         client_secret=REDDIT_CLIENT_SECRET,
                         user_agent=REDDIT_USER_AGENT)
    count = 0
    for sub, query in SEARCHES:
        try:
            for post in reddit.subreddit(sub).search(query, limit=20, sort="new"):
                author = post.author.name if post.author else "deleted"
                src = _upsert_source(db, author, f"https://reddit.com/user/{author}")
                text = f"{post.title}\n\n{post.selftext or ''}".strip()
                if _insert_doc(db, src, "post", post.title,
                               f"https://reddit.com{post.permalink}", text):
                    count += 1
        except Exception as e:
            log.warning("PRAW %s/%s: %s", sub, query, e)
    return count


def _scrape_mock(db):
    count = 0
    for p in MOCK_POSTS:
        src = _upsert_source(db, p["author"], f"https://reddit.com/user/{p['author']}")
        if _insert_doc(db, src, "post", p["title"], p["url"], p["text"]):
            count += 1
    return count


def run():
    db = SessionLocal()
    try:
        if REDDIT_CLIENT_ID:
            log.info("Reddit → PRAW")
            try:
                n = _scrape_praw(db); db.commit()
                log.info("PRAW: %d docs", n); return
            except Exception as e:
                log.warning("PRAW failed: %s", e)

        log.info("Reddit → Arctic Shift (keyless)")
        try:
            n = _scrape_arctic_shift(db); db.commit()
            if n > 0:
                log.info("Arctic Shift: %d new docs", n); return
            log.warning("Arctic Shift: 0 new docs, using mock")
        except Exception as e:
            log.warning("Arctic Shift failed: %s", e)

        log.info("Reddit → mock")
        n = _scrape_mock(db); db.commit()
        log.info("Mock: %d docs", n)
    except Exception as e:
        db.rollback(); log.error("Reddit scraper: %s", e); raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
