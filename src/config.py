"""
Central configuration for the Story Bot.
Loads from environment variables (.env locally, GitHub Secrets in CI).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# ── Instagram ─────────────────────────────────────────────
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# ── YouTube ───────────────────────────────────────────────
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON", "")
YOUTUBE_TOKEN = os.getenv("YOUTUBE_TOKEN_JSON", "")

# ── Channel Settings ──────────────────────────────────────
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Kids Story Time")
# Hindi female neural voice
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "hi-IN-SwaraNeural")
VIDEO_RESOLUTION = os.getenv("VIDEO_RESOLUTION", "1920x1080")
VIDEO_WIDTH, VIDEO_HEIGHT = map(int, VIDEO_RESOLUTION.split("x"))
FPS = int(os.getenv("FPS", "30"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# ── Language ──────────────────────────────────────────────
STORY_LANGUAGE = "hi"          # ISO code
STORY_LANGUAGE_NAME = "Hindi"  # display name

# ── Upload Schedule (local time) ──────────────────────────
UPLOAD_TIMES = ["07:00", "13:00", "18:00"]

# ── Video Duration Target ─────────────────────────────────
TARGET_DURATION_MIN = 40
TARGET_DURATION_MAX = 45
WORDS_PER_MINUTE = 120   # Hindi narration is slightly slower
TARGET_WORD_COUNT = TARGET_DURATION_MIN * WORDS_PER_MINUTE  # ~4800

# ── Paths ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
OVERLAYS_DIR = os.path.join(ASSETS_DIR, "overlays")

for _d in [OUTPUT_DIR, ASSETS_DIR, DATA_DIR, FONTS_DIR, MUSIC_DIR, OVERLAYS_DIR]:
    os.makedirs(_d, exist_ok=True)

# ── Hugging Face Model IDs ────────────────────────────────
HF_CARTOON_MODEL = "OEvortex/cartoon-style"
HF_GHIBLI_MODEL = "OEvortex/ghibli-style"

# ── Safety ────────────────────────────────────────────────
BLOCKED_KEYWORDS = [
    "nude", "naked", "explicit", "obscene", "violence gore",
    "drug", "weapon", "blood", "kill", "murder",
    "अश्लील", "नग्न", "हिंसा", "खून", "नशा", "हत्या",
]

def is_safe_content(text: str) -> bool:
    text_lower = text.lower()
    return not any(kw in text_lower for kw in BLOCKED_KEYWORDS)
