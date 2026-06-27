"""
YouTube Data API v3 integration.
Handles OAuth2 authentication with automatic token refresh,
video upload with scheduled publishing, and thumbnail upload.

OAuth Flow:
  1. First time: run `python -m src.youtube_uploader --auth` locally
     to open a browser and generate token.json
  2. In CI: token.json is written from the YOUTUBE_TOKEN_B64 secret
     and the refresh token is used automatically
"""
import os
import json
import logging
import argparse
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils import logger

# ── Constants ─────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE = "token.json"
YOUTUBE_CATEGORY_ID = "24"  # Entertainment


class YouTubeUploader:
    """Uploads videos and thumbnails to YouTube via Data API v3."""

    def __init__(self):
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        """Load credentials from token.json, refreshing if needed."""
        creds = None

        # Load existing token
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # If no valid credentials, fail with instructions
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing YouTube access token...")
                creds.refresh(Request())
                # Save refreshed token
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
            else:
                raise RuntimeError(
                    "No valid YouTube credentials. Run locally:\n"
                    f"  python -m src.youtube_uploader --auth\n"
                    f"Then store the token.json as a GitHub Secret."
                )

        return build("youtube", "v3", credentials=creds)

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: Optional[str] = None,
        publish_at: Optional[str] = None,
        made_for_kids: bool = True,
    ) -> str:
        """
        Upload a video to YouTube with optional scheduled publishing.

        Args:
            video_path: Path to the MP4 file
            title: Video title (max 100 chars)
            description: Video description
            tags: List of tags
            thumbnail_path: Path to custom thumbnail JPG (1280x720)
            publish_at: ISO 8601 datetime for scheduled publish
                        (e.g. "2026-06-27T07:00:00+05:30")
            made_for_kids: Mark as made for kids (COPPA compliance)

        Returns:
            YouTube video ID
        """
        # Determine privacy status
        if publish_at:
            privacy_status = "private"
            logger.info(f"Uploading with scheduled publish: {publish_at}")
        else:
            privacy_status = "public"
            logger.info("Uploading for immediate publish")

        # Build request body
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": YOUTUBE_CATEGORY_ID,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        if publish_at:
            body["status"]["publishAt"] = publish_at

        # Create media upload (resumable for large files)
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        # Execute upload with progress tracking
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        video_id = self._execute_resumable_upload(request)

        if video_id:
            logger.info(f"YouTube upload successful! Video ID: {video_id}")
            logger.info(f"  URL: https://www.youtube.com/watch?v={video_id}")

            # Upload custom thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                self._upload_thumbnail(video_id, thumbnail_path)
        else:
            raise RuntimeError("YouTube upload failed — no video ID returned")

        return video_id

    def _execute_resumable_upload(self, request) -> Optional[str]:
        """Handle resumable upload with retry and progress logging."""
        max_retries = 3
        response = None
        video_id = None

        for attempt in range(max_retries):
            try:
                while True:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        if progress % 25 == 0:
                            logger.info(f"  Upload progress: {progress}%")
                    if response is not None:
                        if "id" in response:
                            video_id = response["id"]
                        break

                if video_id:
                    break

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    logger.warning(
                        f"  Upload error {e.resp.status}, "
                        f"retrying ({attempt + 1}/{max_retries})"
                    )
                    continue
                else:
                    logger.error(f"  YouTube API error: {e}")
                    raise
            except Exception as e:
                logger.error(f"  Upload exception: {e}")
                if attempt < max_retries - 1:
                    continue
                raise

        return video_id

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """Upload a custom thumbnail for the video."""
        try:
            media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_upload=media,
            ).execute()
            logger.info("  Custom thumbnail uploaded successfully")
        except HttpError as e:
            logger.warning(f"  Thumbnail upload failed: {e}")
        except Exception as e:
            logger.warning(f"  Thumbnail upload error: {e}")

    def get_video_url(self, video_id: str) -> str:
        """Return the standard YouTube watch URL for a video ID."""
        return f"https://www.youtube.com/watch?v={video_id}"


# ── CLI entry point for OAuth flow ────────────────────────
def run_auth_flow():
    """
    Run the OAuth consent flow locally to generate token.json.
    This opens a browser window for you to authorize the app.
    Run: python -m src.youtube_uploader --auth
    """
    if not os.path.exists(CLIENT_SECRETS_FILE):
        logger.error(
            f"'{CLIENT_SECRETS_FILE}' not found. Download it from the "
            "Google Cloud Console (APIs & Services > Credentials)."
        )
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    logger.info(f"OAuth flow complete. Token saved to {TOKEN_FILE}")
    logger.info("For GitHub Actions, encode and store as a secret:")
    logger.info(f"  base64 {TOKEN_FILE}")
    logger.info("Store the output as YOUTUBE_TOKEN_B64 in GitHub Secrets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Uploader")
    parser.add_argument(
        "--auth", action="store_true",
        help="Run OAuth flow to generate token.json",
    )
    args = parser.parse_args()

    if args.auth:
        run_auth_flow()
    else:
        logger.info("Use --auth to run the OAuth flow")
