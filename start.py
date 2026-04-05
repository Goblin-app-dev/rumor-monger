#!/usr/bin/env python3
"""
start.py – Single command to run the entire Warhammer 40k Leak Intel system.

    python start.py

What it does:
  1. Starts Postgres if it isn't running
  2. Creates the DB user + database if they don't exist
  3. Runs the schema migration
  4. Runs scrapers (Reddit + YouTube, no API keys needed)
  5. Extracts claims and scores them
  6. Launches the Streamlit dashboard and opens it in your browser
"""

import os, sys, time, subprocess, platform, webbrowser, socket
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

DB_USER = "warhammer"
DB_PASS = "warhammer"
DB_NAME = "warhammer_leaks"
DB_HOST = "localhost"
DB_PORT = 5432
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
STREAMLIT_PORT = 8501

os.environ["DATABASE_URL"] = DATABASE_URL


# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(msg):
    try:
        width = min(os.get_terminal_size().columns, 70)
    except Exception:
        width = 70
    print("\n" + "─" * width)
    print(f"  {msg}")
    print("─" * width)

def run(cmd, **kwargs):
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=True,
                          capture_output=True, text=True, **kwargs)

def port_open(host, port, timeout=1):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── Step 1: Ensure Postgres is running ───────────────────────────────────────

def ensure_postgres():
    banner("Step 1/5 – Postgres")
    if port_open(DB_HOST, DB_PORT):
        print("  ✓ Postgres already running")
        return

    print("  Starting Postgres …")
    # Try the most common ways to start postgres
    for cmd in [
        "sudo service postgresql start",
        "pg_ctlcluster 15 main start",
        "pg_ctlcluster 14 main start",
        "brew services start postgresql",
        "pg_ctl start",
    ]:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                break
        except Exception:
            continue

    # Wait up to 10s
    for _ in range(10):
        if port_open(DB_HOST, DB_PORT):
            print("  ✓ Postgres started")
            return
        time.sleep(1)

    print("  ✗ Could not start Postgres automatically.")
    print("    Please start it manually, then re-run this script.")
    sys.exit(1)


# ── Step 2: Create DB user + database ────────────────────────────────────────

def ensure_database():
    banner("Step 2/5 – Database setup")
    import psycopg2

    # Try connecting as postgres superuser
    for super_user in ["postgres", os.environ.get("USER", ""), "root"]:
        try:
            conn = psycopg2.connect(dbname="postgres", user=super_user,
                                    host=DB_HOST, port=DB_PORT,
                                    connect_timeout=3)
            conn.autocommit = True
            cur = conn.cursor()

            cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (DB_USER,))
            if not cur.fetchone():
                cur.execute(f"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}'")
                print(f"  ✓ Created user '{DB_USER}'")
            else:
                print(f"  ✓ User '{DB_USER}' exists")

            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER}")
                print(f"  ✓ Created database '{DB_NAME}'")
            else:
                print(f"  ✓ Database '{DB_NAME}' exists")

            cur.close(); conn.close()
            return

        except psycopg2.OperationalError:
            continue
        except Exception as e:
            print(f"  Note: {e}")
            continue

    # If we couldn't connect as superuser, try connecting as warhammer directly
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS,
                                host=DB_HOST, port=DB_PORT, connect_timeout=3)
        conn.close()
        print(f"  ✓ Database '{DB_NAME}' already accessible")
    except Exception as e:
        print(f"  ✗ Could not set up database: {e}")
        print(f"    Run this manually:")
        print(f"      sudo -u postgres psql -c \"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}';\"")
        print(f"      sudo -u postgres psql -c \"CREATE DATABASE {DB_NAME} OWNER {DB_USER};\"")
        sys.exit(1)


# ── Step 3: Run schema migration ─────────────────────────────────────────────

def run_migration():
    banner("Step 3/5 – Schema migration")
    import psycopg2
    sql_path = ROOT / "migrations" / "0001_init_schema.sql"
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS,
                                host=DB_HOST, port=DB_PORT)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql_path.read_text())
        cur.close(); conn.close()
        print("  ✓ Schema up to date")
    except Exception as e:
        print(f"  ✗ Migration failed: {e}")
        sys.exit(1)


# ── Step 4: Run pipeline (scrape → NLP → score) ───────────────────────────────

def run_pipeline():
    banner("Step 4/5 – Data pipeline (scrape → extract → score)")

    steps = [
        ("Reddit scraper",          "scrapers/reddit_scraper.py",              45),
        ("YouTube scraper",         "scrapers/youtube_scraper.py",             70),
        ("Warhammer Community",     "scrapers/wahammer_community_scraper.py",  60),
        ("Claim extraction",        "backend/nlp/claim_extraction.py",         30),
        ("Veracity scoring",        "backend/scoring/veracity_engine.py",      15),
    ]

    for label, script, timeout in steps:
        print(f"  → {label} …", end=" ", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / script)],
                capture_output=True, text=True,
                timeout=timeout,
                env={**os.environ, "DATABASE_URL": DATABASE_URL},
            )
            if result.returncode == 0:
                # Extract the key log line (last INFO line)
                lines = [l for l in result.stderr.splitlines() if "INFO" in l]
                summary = lines[-1].split("INFO ")[-1] if lines else "done"
                print(f"✓  {summary}")
            else:
                print(f"⚠  exited {result.returncode}")
                if result.stderr:
                    print(f"     {result.stderr[-200:]}")
        except subprocess.TimeoutExpired:
            print("⚠  timed out (continuing)")
        except Exception as e:
            print(f"⚠  {e} (continuing)")


# ── Step 5: Launch Streamlit ──────────────────────────────────────────────────

def launch_dashboard():
    banner("Step 5/5 – Launching dashboard")

    # Kill any existing instance on the port
    if port_open(DB_HOST, STREAMLIT_PORT):
        print(f"  Port {STREAMLIT_PORT} already in use — stopping previous instance …")
        subprocess.run(f"pkill -f 'streamlit run' 2>/dev/null || true",
                       shell=True, capture_output=True)
        time.sleep(1)

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(ROOT / "dashboard" / "app.py"),
        "--server.port", str(STREAMLIT_PORT),
        "--server.headless", "true",
        "--server.runOnSave", "true",
        "--browser.gatherUsageStats", "false",
    ]

    env = {**os.environ, "DATABASE_URL": DATABASE_URL}

    print(f"  Starting Streamlit on port {STREAMLIT_PORT} …")
    proc = subprocess.Popen(cmd, env=env, cwd=str(ROOT))

    # Wait until it's ready
    for i in range(20):
        if port_open(DB_HOST, STREAMLIT_PORT):
            break
        time.sleep(0.5)
    else:
        print("  ⚠  Dashboard may not be ready yet, check manually.")

    url = f"http://localhost:{STREAMLIT_PORT}"
    print(f"\n  ✓ Dashboard live at: {url}\n")

    # Try to open browser (works locally; harmlessly fails in Codespaces)
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("  Press Ctrl+C to stop.\n")
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n  Stopping …")
        proc.terminate()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n⚔️  Warhammer 40k 11th Edition Leak Intelligence System")
    print("   Starting up — this takes about 60 seconds on first run.\n")

    ensure_postgres()
    ensure_database()
    run_migration()
    run_pipeline()
    launch_dashboard()
