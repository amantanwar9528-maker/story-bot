"""
Utility functions: logging, file management, text processing,
JSON parsing, and content safety checks.
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR, is_safe_content

# ── Logging Setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("story-bot")


# ── File Helpers ──────────────────────────────────────────
def ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist; return the path."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def clean_output_dir(job_id: str):
    """Remove intermediate files for a completed job to save disk space."""
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    if os.path.exists(job_dir):
        import shutil
        shutil.rmtree(job_dir)
        logger.info(f"Cleaned up intermediate files for job {job_id}")


# ── Text Processing ───────────────────────────────────────
def chunk_text(text: str, max_chars: int = 3000) -> list[str]:
    """
    Split long text into chunks that edge-tts can handle reliably.
    Tries to break at sentence boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (" " + sentence) if current else sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return chunks


def estimate_duration(text: str, wpm: int = 150) -> float:
    """Estimate narration duration in seconds based on word count."""
    words = len(text.split())
    return (words / wpm) * 60


def sanitize_filename(text: str) -> str:
    """Create a filesystem-safe filename from arbitrary text."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text)[:80]


# ── JSON Parsing ──────────────────────────────────────────
def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Robustly extract JSON from an LLM response that may contain
    markdown code fences or extra prose.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    fence_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(fence_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding the first { ... } block
    brace_pattern = r'\{.*\}'
    match = re.search(brace_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.error("Failed to extract JSON from LLM response")
    return None


# ── Content Safety ────────────────────────────────────────
def validate_content_safety(script_data: dict) -> bool:
    """
    Check all narration and visual prompts in the script for
    inappropriate content. Returns True if safe.
    """
    for scene in script_data.get("scenes", []):
        narration = scene.get("narration", "")
        visual = scene.get("visual_prompt", "")

        if not is_safe_content(narration):
            logger.warning(f"Blocked narration content detected in scene")
            return False
        if not is_safe_content(visual):
            logger.warning(f"Blocked visual content detected in scene")
            return False

    return True


# ── Rate Limiting Helper ──────────────────────────────────
def rate_limited_call(func, delay: float = 1.0, *args, **kwargs):
    """Call a function with a delay to respect API rate limits."""
    result = func(*args, **kwargs)
    time.sleep(delay)
    return result
