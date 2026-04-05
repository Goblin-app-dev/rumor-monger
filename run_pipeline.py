"""
Master pipeline runner – executes all steps in order.
Run: python run_pipeline.py
"""
import sys
import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def run_migration():
    log.info("=== Running database migration ===")
    from backend.config import DATABASE_URL
    import psycopg2
    from urllib.parse import urlparse

    u = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        dbname=u.path.lstrip("/"),
        user=u.username,
        password=u.password,
        host=u.hostname,
        port=u.port or 5432,
    )
    conn.autocommit = True
    cur = conn.cursor()
    sql_path = os.path.join(ROOT, "migrations", "0001_init_schema.sql")
    with open(sql_path) as f:
        cur.execute(f.read())
    cur.close()
    conn.close()
    log.info("Migration complete.")


def run_scrapers():
    log.info("=== Running Reddit scraper ===")
    from scrapers.reddit_scraper import run as reddit_run
    reddit_run()

    log.info("=== Running YouTube scraper ===")
    from scrapers.youtube_scraper import run as youtube_run
    youtube_run()

    log.info("=== Running Warhammer Community scraper ===")
    from scrapers.wahammer_community_scraper import run as warcom_run
    warcom_run()


def run_nlp():
    log.info("=== Running claim extraction ===")
    from backend.nlp.claim_extraction import run as extract_run
    extract_run()


def run_scoring():
    log.info("=== Running veracity engine ===")
    from backend.scoring.veracity_engine import run as score_run
    score_run()


if __name__ == "__main__":
    run_migration()
    run_scrapers()
    run_nlp()
    run_scoring()
    log.info("=== Pipeline complete. Launch dashboard with: streamlit run dashboard/app.py ===")
