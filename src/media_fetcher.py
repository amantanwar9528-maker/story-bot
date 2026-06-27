"""
Fetches high-quality royalty-free stock videos and images from
Pexels and Pixabay APIs. Used to supplement AI-generated cartoon
illustrations with real footage for transitions, establishing
shots, and visual variety.
"""
import os
import time
import logging
import requests
from typing import Optional
from urllib.parse import quote

from config import PEXELS_API_KEY, PIXABAY_API_KEY, OUTPUT_DIR
from utils import logger, ensure_dir

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"
PIXABAY_PHOTO_URL = "https://pixabay.com/api/"


class MediaFetcher:
    """Fetches stock media from Pexels and Pixabay (both free)."""

    def __init__(self):
        self.pexels_headers = {"Authorization": PEXELS_API_KEY}
        self.pixabay_params_base = {"key": PIXABAY_API_KEY}

    # ── Pexels ───────────────────────────────────────────────
    def _pexels_search_videos(
        self, query: str, per_page: int = 5
    ) -> list[dict]:
        """Search Pexels for royalty-free videos matching the query."""
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",
            "size": "large",
        }
        try:
            resp = requests.get(
                PEXELS_VIDEO_URL,
                headers=self.pexels_headers,
                params=params,
                timeout=30,
            )
            if resp.status_code == 200:
                videos = resp.json().get("videos", [])
                results = []
                for v in videos:
                    # Pick the best quality file under 50MB
                    best_file = None
                    for f in v.get("video_files", []):
                        if f.get("width", 0) >= 1280:
                            if best_file is None or f.get("width", 0) > best_file.get("width", 0):
                                best_file = f
                    if best_file:
                        results.append({
                            "url": best_file["link"],
                            "width": best_file.get("width"),
                            "height": best_file.get("height"),
                            "duration": v.get("duration"),
                            "source": "pexels",
                        })
                return results
            logger.warning(f"Pexels video search failed: {resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Pexels video request error: {e}")
        return []

    def _pexels_search_photos(
        self, query: str, per_page: int = 5
    ) -> list[dict]:
        """Search Pexels for royalty-free photos matching the query."""
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",
        }
        try:
            resp = requests.get(
                PEXELS_PHOTO_URL,
                headers=self.pexels_headers,
                params=params,
                timeout=30,
            )
            if resp.status_code == 200:
                photos = resp.json().get("photos", [])
                return [
                    {
                        "url": p["src"]["large2x"],
                        "width": p.get("width"),
                        "height": p.get("height"),
                        "source": "pexels",
                    }
                    for p in photos
                ]
            logger.warning(f"Pexels photo search failed: {resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Pexels photo request error: {e}")
        return []

    # ── Pixabay ──────────────────────────────────────────────
    def _pixabay_search_videos(
        self, query: str, per_page: int = 5
    ) -> list[dict]:
        """Search Pixabay for royalty-free videos."""
        params = {
            **self.pixabay_params_base,
            "q": query,
            "per_page": per_page,
            "video_type": "all",
            "order": "popular",
        }
        try:
            resp = requests.get(PIXABAY_VIDEO_URL, params=params, timeout=30)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                results = []
                for h in hits:
                    # Prefer large or medium quality
                    v = h.get("videos", {})
                    for quality_key in ["large", "medium", "small"]:
                        q = v.get(quality_key, {})
                        if q.get("url"):
                            results.append({
                                "url": q["url"],
                                "width": q.get("width"),
                                "height": q.get("height"),
                                "duration": h.get("duration"),
                                "source": "pixabay",
                            })
                            break
                return results
            logger.warning(f"Pixabay video search failed: {resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Pixabay video request error: {e}")
        return []

    def _pixabay_search_photos(
        self, query: str, per_page: int = 5
    ) -> list[dict]:
        """Search Pixabay for royalty-free photos."""
        params = {
            **self.pixabay_params_base,
            "q": query,
            "per_page": per_page,
            "image_type": "photo",
            "orientation": "horizontal",
            "order": "popular",
        }
        try:
            resp = requests.get(PIXABAY_PHOTO_URL, params=params, timeout=30)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                return [
                    {
                        "url": h["largeImageURL"],
                        "width": h.get("imageWidth"),
                        "height": h.get("imageHeight"),
                        "source": "pixabay",
                    }
                    for h in hits
                ]
            logger.warning(f"Pixabay photo search failed: {resp.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Pixabay photo request error: {e}")
        return []

    # ── Download ─────────────────────────────────────────────
    def _download_file(self, url: str, output_path: str) -> Optional[str]:
        """Download a file from URL to local path."""
        try:
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return output_path
            logger.warning(f"Download failed ({resp.status_code}): {url[:80]}")
        except requests.RequestException as e:
            logger.warning(f"Download error: {e}")
        return None

    # ── Public API ───────────────────────────────────────────
    def fetch_stock_media(
        self,
        query: str,
        job_dir: str,
        media_type: str = "video",
        count: int = 3,
    ) -> list[str]:
        """
        Fetch stock media (video or image) for a given query.
        Tries Pexels first, then Pixabay as fallback.
        Returns list of local file paths.
        """
        media_dir = os.path.join(job_dir, "stock_media")
        ensure_dir(media_dir)

        results = []

        # Try Pexels first
        if media_type == "video":
            pexels_results = self._pexels_search_videos(query, per_page=count)
        else:
            pexels_results = self._pexels_search_photos(query, per_page=count)

        # If Pexels didn't return enough, try Pixabay
        if len(pexels_results) < count:
            if media_type == "video":
                pixabay_results = self._pixabay_search_videos(
                    query, per_page=count - len(pexels_results)
                )
            else:
                pixabay_results = self._pixabay_search_photos(
                    query, per_page=count - len(pexels_results)
                )
            pexels_results.extend(pixabay_results)

        # Download each file
        for i, item in enumerate(pexels_results[:count]):
            ext = ".mp4" if media_type == "video" else ".jpg"
            filename = f"stock_{i:03d}_{item['source']}{ext}"
            filepath = os.path.join(media_dir, filename)

            downloaded = self._download_file(item["url"], filepath)
            if downloaded:
                results.append(downloaded)
                logger.info(f"  Downloaded stock {media_type}: {filename}")
            time.sleep(0.5)  # polite delay

        logger.info(
            f"Fetched {len(results)} stock {media_type} items for '{query}'"
        )
        return results

    def fetch_channel_intro_clip(self, job_dir: str) -> Optional[str]:
        """
        Fetch a generic 'children animation' or 'cartoon' stock clip
        to use as a channel intro / bumper between scenes.
        """
        clips = self.fetch_stock_media(
            query="cartoon animation colorful",
            job_dir=job_dir,
            media_type="video",
            count=1,
        )
        return clips[0] if clips else None
