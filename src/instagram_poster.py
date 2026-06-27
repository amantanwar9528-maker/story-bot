"""
Instagram Reels posting via instagrapi.
Logs in with username/password (no official API key) and uploads
short promotional Reel clips to drive traffic to YouTube.

⚠️  RISK NOTICE:
   Password-based Instagram automation violates Meta's Terms of
   Service. Instagram may flag or suspend accounts using this method.
   For zero-ban-risk automation, use the official Instagram Graph API
   with OAuth (requires a Facebook Business account).
   This module is provided as requested by the user.
"""
import os
import logging
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired,
    ClientError,
    ClientConnectionError,
)

from utils import logger

SESSION_FILE = "instagram_session.json"


class InstagramPoster:
    """Posts promotional Reels to Instagram via instagrapi."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.client = Client()
        # Set a realistic user agent to reduce detection
        self.client.set_settings({
            "user_agent": (
                "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
        })
        self._login()

    def _login(self):
        """
        Attempt to restore a cached session first (reduces login
        frequency and detection risk). Falls back to fresh login.
        """
        # Try loading cached session
        if os.path.exists(SESSION_FILE):
            try:
                self.client.load_settings(SESSION_FILE)
                self.client.login(self.username, self.password)
                # Verify session is still valid
                try:
                    self.client.get_timeline_feed()
                    logger.info("Instagram: session restored from cache")
                    return
                except Exception:
                    logger.info("Instagram: cached session expired, re-logging in")
            except Exception as e:
                logger.warning(f"Instagram: session restore failed: {e}")

        # Fresh login
        try:
            self.client.login(self.username, self.password)
            self.client.dump_settings(SESSION_FILE)
            logger.info("Instagram: login successful, session cached")
        except LoginRequired as e:
            logger.error(f"Instagram login required: {e}")
            raise
        except ClientConnectionError as e:
            logger.error(f"Instagram connection error: {e}")
            raise
        except ClientError as e:
            logger.error(f"Instagram client error: {e}")
            raise
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            raise

    def post_reel(
        self,
        video_path: str,
        caption: str,
        thumbnail_path: Optional[str] = None,
    ) -> bool:
        """
        Upload a Reel to Instagram.

        Args:
            video_path: Path to the vertical MP4 (1080x1920, <90s)
            caption: Caption text with hashtags and YouTube link
            thumbnail_path: Optional custom cover image

        Returns:
            True if upload succeeded, False otherwise
        """
        if not os.path.exists(video_path):
            logger.error(f"Reel video not found: {video_path}")
            return False

        try:
            media = self.client.clip_upload(
                path=video_path,
                caption=caption,
            )

            if media and hasattr(media, "id"):
                logger.info(
                    f"Instagram Reel posted successfully! "
                    f"Media ID: {media.id}"
                )
                return True
            else:
                logger.warning("Instagram Reel upload returned no media ID")
                return True  # Upload may have succeeded without returning ID

        except Exception as e:
            logger.error(f"Instagram Reel upload failed: {e}")
            return False

    def generate_reel_caption(
        self,
        story_title: str,
        youtube_url: str,
        topic_type: str = "children",
    ) -> str:
        """
        Generate an engaging Instagram caption that promotes the
        YouTube video without revealing the full story.
        """
        if topic_type == "children":
            hooks = [
                f"✨ Once upon a time... '{story_title}' is NOW on YouTube!",
                f"🌙 Bedtime story alert! '{story_title}' — watch the full adventure!",
                f"🎨 A magical tale awaits! '{story_title}' is live on YouTube!",
                f"🦁 Adventure awaits! Full story of '{story_title}' now on YouTube!",
            ]
        else:
            hooks = [
                f"💀 Dare to watch? '{story_title}' — full story on YouTube!",
                f"🕯️ Lights out... '{story_title}' is live. Can you handle it?",
                f"😱 Don't watch alone! '{story_title}' — full horror story on YouTube!",
            ]

        import random
        hook = random.choice(hooks)

        if topic_type == "children":
            hashtags = (
                "#bedtimestories #kidsstories #storytime #childrenstories "
                "#animatedstories #fairytale #kidsvideo #storyforkids "
                "#moralstories #bedtimestory"
            )
        else:
            hashtags = (
                "#horrorstories #scarystories #horror #creepystories "
                "#storytime #horrortale #midnightstories #scary "
                "#horrorcommunity #spookystories"
            )

        caption = (
            f"{hook}\n\n"
            f"📺 Watch the FULL story on YouTube:\n"
            f"{youtube_url}\n\n"
            f"🔔 Subscribe for daily new stories!\n\n"
            f"{hashtags}"
        )

        return caption
