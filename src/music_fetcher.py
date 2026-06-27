"""
Fetches royalty-free background music from Pixabay and falls back
to pre-bundled tracks in the assets/music directory.
Music is ducked (volume lowered) during narration and raised
during scene transitions.
"""
import os
import time
import logging
import requests
from typing import Optional

from config import PIXABAY_API_KEY, MUSIC_DIR
from utils import logger, ensure_dir

PIXABAY_MUSIC_URL = "https://pixabay.com/api/music/"


class MusicFetcher:
    """Fetches royalty-free background music from Pixabay."""

    def __init__(self):
        self.params_base = {"key": PIXABAY_API_KEY}

    def search_music(
        self,
        mood: str = "happy",
        count: int = 3,
    ) -> list[dict]:
        """
        Search Pixabay for music matching the mood.
        Returns list of dicts with url, title, duration.
        """
        # Map story moods to Pixabay search terms
        mood_to_query = {
            "happy": "happy cheerful upbeat",
            "excited": "energetic fun playful",
            "sad": "sad emotional piano",
            "mysterious": "mysterious ambient",
            "scary": "suspense dark horror",
            "tense": "tense suspense thriller",
            "peaceful": "peaceful calm relaxing",
            "neutral": "background ambient soft",
        }
        query = mood_to_query.get(mood, "background ambient soft")

        params = {
            **self.params_base,
            "q": query,
            "per_page": count,
            "order": "popular",
        }

        try:
            resp = requests.get(PIXABAY_MUSIC_URL, params=params, timeout=30)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                return [
                    {
                        "url": h.get("audio"),
                        "title": h.get("title", "unknown"),
                        "duration": h.get("duration"),
                        "source": "pixabay",
                    }
                    for h in hits
                    if h.get("audio")
                ]
            logger.warning(f"Pixabay music search failed: {resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Pixabay music request error: {e}")
        return []

    def _download_file(self, url: str, output_path: str) -> Optional[str]:
        """Download a music file from URL."""
        try:
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return output_path
        except requests.RequestException as e:
            logger.warning(f"Music download error: {e}")
        return None

    def _get_bundled_track(self, mood: str) -> Optional[str]:
        """
        Return a pre-bundled royalty-free track from assets/music/.
        These are tracks you manually place in the folder as a fallback.
        """
        if not os.path.exists(MUSIC_DIR):
            return None

        mood_prefixes = {
            "happy": "happy_",
            "excited": "excited_",
            "sad": "sad_",
            "scary": "scary_",
            "tense": "tense_",
            "peaceful": "peaceful_",
            "neutral": "bg_",
        }
        prefix = mood_prefixes.get(mood, "bg_")

        # Find any matching file
        for fname in os.listdir(MUSIC_DIR):
            if fname.lower().startswith(prefix) and fname.endswith((".mp3", ".wav", ".m4a")):
                return os.path.join(MUSIC_DIR, fname)

        # Fall back to any music file
        for fname in os.listdir(MUSIC_DIR):
            if fname.endswith((".mp3", ".wav", ".m4a")):
                return os.path.join(MUSIC_DIR, fname)

        return None

    def fetch_background_music(
        self,
        mood: str,
        job_dir: str,
    ) -> Optional[str]:
        """
        Fetch a background music track matching the mood.
        Tries Pixabay API first, then bundled tracks as fallback.
        Returns path to the downloaded/selected music file.
        """
        music_dir = os.path.join(job_dir, "music")
        ensure_dir(music_dir)

        # Try Pixabay API
        tracks = self.search_music(mood=mood, count=3)
        for i, track in enumerate(tracks):
            output_path = os.path.join(music_dir, f"bg_music_{i:03d}.mp3")
            downloaded = self._download_file(track["url"], output_path)
            if downloaded:
                logger.info(
                    f"Downloaded background music: '{track['title']}' "
                    f"({track.get('duration', '?')}s)"
                )
                return downloaded
            time.sleep(0.5)

        # Fallback to bundled tracks
        logger.info("Pixabay music unavailable, using bundled track")
        bundled = self._get_bundled_track(mood)
        if bundled:
            logger.info(f"Using bundled music: {os.path.basename(bundled)}")
            return bundled

        logger.warning("No background music available — proceeding without")
        return None
