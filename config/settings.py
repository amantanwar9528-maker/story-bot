"""
Story Bot Configuration
All settings, API keys, and schedules in one place.
"""
import os
from pathlib import Path

# ============================================================
# PROJECT PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"
SECRETS_DIR = BASE_DIR / "secrets"

for d in [ASSETS_DIR, OUTPUT_DIR, DATA_DIR, SECRETS_DIR,
          ASSETS_DIR/"audio", ASSETS_DIR/"images",
          ASSETS_DIR/"videos", ASSETS_DIR/"thumbnails",
          ASSETS_DIR/"music", OUTPUT_DIR/"final_videos"]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# SCHEDULE (3 uploads per day)
# ============================================================
UPLOAD_SCHEDULE = {
    "morning":   {"hour": 7,  "minute": 0},   # 7 AM
    "afternoon": {"hour": 13, "minute": 0},   # 1 PM
    "evening":   {"hour": 18, "minute": 0},   # 6 PM
}

# ============================================================
# STORY SETTINGS
# ============================================================
MAX_VIDEO_DURATION_MIN = 45          # cap at ~45 minutes
TARGET_DURATION_MIN     = 30         # aim for ~30 min average
STORY_GENRES            = ["children", "horror"]
PRIMARY_GENRE           = "children"  # main channel topic

# Gutenberg bookshelf IDs (children's literature)
GUTENBERG_BOOKSHELVES = {
    "children": "Children's Literature",
    "horror":   "Gothic Fiction",
}

# ============================================================
# TTS — edge-tts (FREE, no API key)
# ============================================================
TTS_CONFIG = {
    "voice":      "en-US-AriaNeural",      # natural female voice
    "alt_voice":  "en-US-GuyNeural",       # natural male voice
    "rate":       "+5%",                    # slightly faster for engagement
    "volume":     "+0%",
    "output_fmt": "audio-24khz-48kbitrate-mono-mp3",
}

# ============================================================
# IMAGE GENERATION — Pollinations.ai (FREE, no API key)
# ============================================================
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
IMAGE_CONFIG = {
    "model":        "flux",                 # free model
    "width":        1280,
    "height":       720,
    "seed":         None,                   # random each time
    "nologo":       True,
    "cartoon_style": "cartoon style, colorful, child-friendly, "
                     "Studio Ghibli inspired, soft lighting, "
                     "whimsical, storybook illustration, high quality",
    "ghibli_style":  "Studio Ghibli style, anime, watercolor, "
                     "dreamy, soft pastel colors, Hayao Miyazaki, "
                     "beautiful detailed background, masterpiece",
}

# ============================================================
# STOCK VIDEO — Pexels & Pixabay (FREE APIs)
# ============================================================
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

STOCK_SEARCH_TERMS = {
    "children": ["cartoon", "animation", "kids playing", "fairy tale",
                 "magical forest", "castle", "animals cartoon"],
    "horror":   ["dark forest", "mysterious", "fog", "spooky",
                 "night sky", "abandoned"],
}

# ============================================================
# MUSIC — Pixabay Music API (FREE, royalty-free)
# ============================================================
MUSIC_CONFIG = {
    "mood_children": "happy, cheerful, playful, whimsical",
    "mood_horror":   "dark, suspense, eerie, ambient",
    "min_duration":  60,
    "max_duration":  300,
}

# ============================================================
# YOUTUBE — Data API v3 (FREE, OAuth 2.0)
# ============================================================
YOUTUBE_CONFIG = {
    "client_secrets_file": str(SECRETS_DIR / "client_secrets.json"),
    "token_file":          str(SECRETS_DIR / "youtube_token.json"),
    "scopes": ["https://www.googleapis.com/auth/youtube.upload",
               "https://www.googleapis.com/auth/youtube"],
    "category_id": "24",    # Entertainment
    "privacy":    "public",
    "tags":       ["children stories", "bedtime stories",
                   "storytelling", "kids", "fairy tale",
                   "animated story", "audio story"],
}

# ============================================================
# INSTAGRAM — Playwright (ID/password, no API)
# ============================================================
INSTAGRAM_CONFIG = {
    "credentials_file": str(SECRETS_DIR / "instagram_creds.json"),
    "reel_duration_sec": 20,    # short promo clip
    "caption_template": "🎬 New story on YouTube! Watch full video → link in bio\n"
                        "#childrenstories #bedtimestories #storytime #kids",
}

# ============================================================
# AI SCRIPT WRITING
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # you have paid version
GEMINI_MODEL = "gemini-2.0-flash"

SCRIPT_CONFIG = {
    "system_prompt": (
        "You are a master storyteller for a YouTube children's story channel. "
        "Rewrite the given story into an engaging narration script suitable "
        "for a {duration}-minute video. Use vivid descriptions, dramatic "
        "pauses (marked as [PAUSE]), and scene break markers (marked as "
        "[SCENE: description]). Make it captivating for children while "
        "keeping it family-friendly. For horror stories, make it spooky "
        "but not graphic or inappropriate."
    ),
    "max_tokens": 8000,
    "temperature": 0.8,
}

# ============================================================
# CONTENT SAFETY
# ============================================================
SAFETY_CONFIG = {
    "blocked_terms": [
        "explicit", "sexual", "violence graphic", "drug",
        "weapon", "profanity", "obscene", "nudity",
    ],
    "use_ai_filter": True,   # use Gemini to double-check
}
