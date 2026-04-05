# ⚔️ Warhammer 40k 11th Edition Leak Intelligence System

Track, score, and visualise 11th edition rumours scraped live from Reddit and YouTube.

## One command

```bash
python start.py
```

That's it. `start.py` handles everything automatically:

| Step | What happens |
|------|-------------|
| 1 | Starts Postgres if it isn't running |
| 2 | Creates the DB user + database if missing |
| 3 | Runs the schema migration (idempotent) |
| 4 | Scrapes Reddit via Arctic Shift (no API key needed) |
| 4 | Scrapes YouTube via yt-dlp (no API key needed) |
| 4 | Extracts claims using keyword NLP |
| 4 | Scores claims by evidence count + source reputation |
| 5 | Launches the Streamlit dashboard and opens your browser |

## Requirements

```bash
pip install -r requirements.txt
```

Postgres must be installed (it does **not** need to be running — `start.py` starts it).

## API keys (optional)

Without keys the system uses Arctic Shift + yt-dlp to pull real public data.
Add keys to `.env` for deeper coverage:

| Key | Source |
|-----|--------|
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | reddit.com/prefs/apps |
| `YOUTUBE_API_KEY` | console.cloud.google.com → YouTube Data API v3 |

```bash
cp .env.example .env   # then fill in your keys
python start.py
```

## Dashboard pages

| Page | Description |
|------|-------------|
| Home | Rumour feed — confidence badges, colour bars, click for details |
| Claim Detail | Full text, all evidence sources, manual status override |
| Claims Browser | Sortable/filterable table of all claims |
| Sources Intel | Source list with editable reputation scores |
| Rumour Network | Interactive claim–source graph |

## Confidence tiers

| Status | Meaning |
|--------|---------|
| ✅ Confirmed | 5+ independent sources, high reputation |
| 🟢 Likely | 3+ independent sources |
| 🟡 Plausible | 2 sources or transcript evidence |
| 🟠 Unsubstantiated | Single low-reputation source |
| ⛔ Debunked | Manually marked false |
