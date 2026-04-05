"""
YouTube scraper – yt-dlp for search (no API key), plus transcript extraction.
Scoped to 5 videos max with tight timeouts to stay fast.
Falls back to YouTube Data API v3 (if key set) or mock data.
"""
import hashlib, logging, subprocess, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backend.config import YOUTUBE_API_KEY, YOUTUBE_SEARCH_TERMS
from backend.db import SessionLocal
from backend.models import Source, Document

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MOCK_VIDEOS = [
    {"channel": "Auspex Tactics", "channel_url": "https://youtube.com/@AuspexTactics",
     "title": "11th Edition Leak – Full Rules Breakdown",
     "url": "https://youtube.com/watch?v=mock1",
     "transcript": ("Space Marines getting toughness 5 on Intercessors in 11th edition. "
                    "Detachment rules replacing chapter tactics entirely. Stratagems capped "
                    "at 2 per phase. Weapons now included in datasheet points cost.")},
    {"channel": "Chapter Master Valrak", "channel_url": "https://youtube.com/@ChapterMasterValrak",
     "title": "What We Know About 11th Edition So Far",
     "url": "https://youtube.com/watch?v=mock2",
     "transcript": ("Multiple sources confirm Intercessors toughness 5 in 11th edition. "
                    "Necron Warriors also toughness 5. Objective control for monsters 3 OC default. "
                    "Tyranid synapse gives battleshock immunity within 6 inches. "
                    "Points coming down – Intercessors around 18 points each.")},
    {"channel": "Mordian Glory", "channel_url": "https://youtube.com/@MordianGlory",
     "title": "Two Small 11th Edition Leaks Confirmed",
     "url": "https://youtube.com/watch?v=mock3",
     "transcript": ("Detachment system replaces chapter tactics – unique army rule per detachment. "
                    "Stratagem phase cap confirmed at 2 stratagems per phase. "
                    "Weapon costs included in datasheet points confirmed by my source.")},
    {"channel": "Discourse Minis", "channel_url": "https://youtube.com/@DiscourseMinis",
     "title": "Warhammer 11th Edition Just Got Leaked",
     "url": "https://youtube.com/watch?v=mock4",
     "transcript": ("Toughness values going up across all factions in 11th edition. "
                    "Space Marines toughness 5, Necrons toughness 5, Orks toughness 5 on Boyz. "
                    "Points coming down to compensate. Detachment overhaul confirmed.")},
]


def _sha256(t): return hashlib.sha256(t.encode()).hexdigest()

def _upsert_source(db, handle, url):
    s = db.query(Source).filter_by(platform="youtube", handle=handle).first()
    if not s:
        s = Source(platform="youtube", handle=handle, url=url, reputation_score=0.5)
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


def _parse_vtt(raw):
    """Strip VTT markup, deduplicate lines, return clean text."""
    seen, lines = set(), []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line or line.startswith("NOTE"):
            continue
        clean = re.sub(r'<[^>]+>', '', line).strip()
        if clean and clean not in seen:
            lines.append(clean)
            seen.add(clean)
    return " ".join(lines)


def _scrape_ytdlp(db):
    count = 0
    # Use only the first search term to stay fast; yt-dlp search is slow
    term = YOUTUBE_SEARCH_TERMS[0]
    log.info("yt-dlp search: %s", term)

    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "-j", "--no-warnings",
             f"ytsearch5:{term}"],
            capture_output=True, text=True, timeout=25
        )
        videos = []
        for line in result.stdout.strip().splitlines():
            try:
                v = __import__('json').loads(line)
                videos.append((v.get("id",""), v.get("title",""),
                               v.get("channel","unknown"), v.get("channel_url","")))
            except Exception:
                continue
        log.info("Found %d videos", len(videos))
    except Exception as e:
        log.warning("yt-dlp search failed: %s", e)
        return 0

    for vid_id, title, channel, ch_url in videos[:5]:
        if not vid_id:
            continue
        video_url = f"https://www.youtube.com/watch?v={vid_id}"
        src = _upsert_source(db, channel, ch_url or f"https://youtube.com")

        # Metadata doc (title only – skip slow description fetch)
        _insert_doc(db, src, "video", title, video_url, f"{title}\n\n40k 11th edition video.")

        # Transcript via yt-dlp auto-subs
        vtt_base = f"/tmp/ytsub_{vid_id}"
        vtt_path = f"{vtt_base}.en.vtt"
        try:
            subprocess.run(
                ["yt-dlp", "--skip-download", "--write-auto-subs",
                 "--sub-format", "vtt", "--sub-langs", "en",
                 "-o", vtt_base, "--no-warnings", video_url],
                capture_output=True, text=True, timeout=20
            )
            if os.path.exists(vtt_path):
                with open(vtt_path) as f:
                    transcript = _parse_vtt(f.read())
                os.remove(vtt_path)
                if len(transcript) > 100:
                    if _insert_doc(db, src, "transcript",
                                   f"Transcript: {title}", video_url, transcript):
                        count += 1
                        log.info("+ transcript: %s", title[:60])
        except Exception as e:
            log.debug("Transcript %s: %s", vid_id, e)

    return count


def _scrape_api(db):
    from googleapiclient.discovery import build
    from youtube_transcript_api import YouTubeTranscriptApi
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    count = 0
    for term in YOUTUBE_SEARCH_TERMS:
        resp = youtube.search().list(q=term, part="snippet", type="video",
                                     maxResults=8, relevanceLanguage="en").execute()
        for item in resp.get("items", []):
            vid_id  = item["id"]["videoId"]
            snippet = item["snippet"]
            title   = snippet.get("title", "")
            ch      = snippet.get("channelTitle", "unknown")
            ch_url  = f"https://youtube.com/channel/{snippet.get('channelId','')}"
            url     = f"https://youtube.com/watch?v={vid_id}"
            src = _upsert_source(db, ch, ch_url)
            _insert_doc(db, src, "video", title, url,
                        f"{title}\n\n{snippet.get('description','')}")
            try:
                parts = YouTubeTranscriptApi.get_transcript(vid_id)
                tx = " ".join(p["text"] for p in parts)
                if _insert_doc(db, src, "transcript", f"Transcript: {title}", url, tx):
                    count += 1
            except Exception:
                pass
    return count


def _scrape_mock(db):
    count = 0
    for v in MOCK_VIDEOS:
        src = _upsert_source(db, v["channel"], v["channel_url"])
        _insert_doc(db, src, "video", v["title"], v["url"], v["title"])
        if _insert_doc(db, src, "transcript", f"Transcript: {v['title']}",
                       v["url"], v["transcript"]):
            count += 1
    return count


def run():
    db = SessionLocal()
    try:
        if YOUTUBE_API_KEY:
            log.info("YouTube → Data API v3")
            try:
                n = _scrape_api(db); db.commit()
                log.info("API: %d docs", n); return
            except Exception as e:
                log.warning("YouTube API failed: %s", e)

        log.info("YouTube → yt-dlp (keyless)")
        try:
            n = _scrape_ytdlp(db); db.commit()
            if n > 0:
                log.info("yt-dlp: %d new docs", n); return
            log.warning("yt-dlp: 0 transcript docs, using mock")
        except Exception as e:
            log.warning("yt-dlp failed: %s", e)

        log.info("YouTube → mock")
        n = _scrape_mock(db); db.commit()
        log.info("Mock: %d docs", n)
    except Exception as e:
        db.rollback(); log.error("YouTube scraper: %s", e); raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
