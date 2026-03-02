"""
Central configuration: loads env vars and exposes constants.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DOTENV_PATH = BASE_DIR / ".env"

load_dotenv(DOTENV_PATH)

# ── Streamlit Cloud secrets fallback ──
def _from_st_secrets(key):
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

def get_env(key, default=None):
    return os.environ.get(key) or _from_st_secrets(key) or default

# ── AI Keys ──
GEMINI_API_KEY = get_env("GEMINI_API_KEY")
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")

# ── LinkedIn ──
LINKEDIN_CLIENT_ID = get_env("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = get_env("LINKEDIN_CLIENT_SECRET")
LINKEDIN_ORG_ID = get_env("LINKEDIN_ORG_ID")
LINKEDIN_ACCESS_TOKEN = get_env("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_TOKEN_EXPIRY = get_env("LINKEDIN_TOKEN_EXPIRY")
LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202601"

# ── Firebase ──
FIREBASE_SERVICE_ACCOUNT = get_env("FIREBASE_SERVICE_ACCOUNT")

# ── Local Paths ──
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

INSPIRATIONS_FILE = DATA_DIR / "inspirations.json"
QA_RECORDS_FILE = DATA_DIR / "qa_records.json"
BRAND_PROFILE_FILE = DATA_DIR / "brand_profile.json"
SCHEDULE_FILE = DATA_DIR / "schedule.json"
POSTS_FILE = DATA_DIR / "posts.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"

# ── Content Types ──
CONTENT_TYPES = {
    "opinion": {"label": "觀點文", "emoji": "🔴", "color": "#ef4444"},
    "tutorial": {"label": "教學文", "emoji": "🟡", "color": "#eab308"},
    "trend": {"label": "趨勢文", "emoji": "🟢", "color": "#22c55e"},
}

# ── Post Statuses ──
POST_STATUSES = ["draft", "review", "approved", "scheduled", "published"]
