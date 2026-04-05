"""
Central configuration – reads from Streamlit secrets first, then environment
variables, then falls back to localhost defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root when running locally
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=False)


def _secret(key: str, default: str = "") -> str:
    """Return value from st.secrets (Streamlit Cloud) or os.environ."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


DATABASE_URL: str = _secret(
    "DATABASE_URL",
    "postgresql://warhammer:warhammer@localhost:5432/warhammer_leaks",
)

REDDIT_CLIENT_ID:     str = _secret("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = _secret("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT:    str = _secret("REDDIT_USER_AGENT", "warhammer-leak-intel/1.0")
YOUTUBE_API_KEY:      str = _secret("YOUTUBE_API_KEY", "")

# Subreddits to scrape
SUBREDDITS = [
    "Warhammer40k",
    "WarhammerCompetitive",
    "warhammer",
    "40kLore",
]

# YouTube search terms
YOUTUBE_SEARCH_TERMS = [
    "Warhammer 40k 11th edition leak",
    "Warhammer 40000 11th edition rumour",
    "40k 11th edition new rules",
]

# Claim extraction keywords
CLAIM_KEYWORDS = [
    "toughness", "strength", "wounds", "attacks", "save", "points",
    "detachment", "stratagem", "datasheet", "ability", "weapon skill",
    "ballistic skill", "leadership", "objective control", "keywords",
    "11th edition", "new edition", "rule change", "rule of cool",
    "index", "codex", "faction rule", "army rule", "enhancement",
]

# Faction keywords for tagging
FACTION_KEYWORDS = {
    "space marines":      ["space marine", "adeptus astartes", "chapter"],
    "chaos space marines":["chaos space marine", "heretic astartes"],
    "necrons":            ["necron"],
    "orks":               ["ork", "waaagh"],
    "tyranids":           ["tyranid", "hive mind", "synapse"],
    "eldar":              ["aeldari", "eldar", "craftworld"],
    "tau":                ["t'au", "tau", "greater good"],
    "imperial guard":     ["astra militarum", "imperial guard", "guard"],
    "death guard":        ["death guard", "nurgle"],
    "thousand sons":      ["thousand sons", "tzeentch"],
    "world eaters":       ["world eaters", "khorne"],
    "emperors children":  ["emperor's children", "slaanesh"],
}
