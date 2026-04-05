"""
Central configuration loaded from environment variables / .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=False)

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://warhammer:warhammer@localhost:5432/warhammer_leaks",
)

REDDIT_CLIENT_ID: str = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT: str = os.environ.get(
    "REDDIT_USER_AGENT", "warhammer-leak-intel/1.0"
)

YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")

# Subreddits to scrape
SUBREDDITS = [
    "Warhammer40k",
    "WarhammerCompetitive",
    "warhammer",
    "40kLore",
]

# YouTube search terms to hunt leaks
YOUTUBE_SEARCH_TERMS = [
    "Warhammer 40k 11th edition leak",
    "Warhammer 40000 11th edition rumour",
    "40k 11th edition new rules",
]

# Claim extraction keywords (any sentence containing these is a candidate claim)
CLAIM_KEYWORDS = [
    "toughness", "strength", "wounds", "attacks", "save", "points",
    "detachment", "stratagem", "datasheet", "ability", "weapon skill",
    "ballistic skill", "leadership", "objective control", "keywords",
    "11th edition", "new edition", "rule change", "rule of cool",
    "index", "codex", "faction rule", "army rule", "enhancement",
]

# Faction keywords for tagging
FACTION_KEYWORDS = {
    "space marines": ["space marine", "adeptus astartes", "chapter"],
    "chaos space marines": ["chaos space marine", "heretic astartes"],
    "necrons": ["necron"],
    "orks": ["ork", "waaagh"],
    "tyranids": ["tyranid", "hive mind", "synapse"],
    "eldar": ["aeldari", "eldar", "craftworld"],
    "tau": ["t'au", "tau", "greater good"],
    "imperial guard": ["astra militarum", "imperial guard", "guard"],
    "death guard": ["death guard", "nurgle"],
    "thousand sons": ["thousand sons", "tzeentch"],
    "world eaters": ["world eaters", "khorne"],
    "emperors children": ["emperor's children", "slaanesh"],
}
