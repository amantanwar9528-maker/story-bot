"""
Ghibli-style thumbnail generator.
Creates an eye-catching YouTube thumbnail for each story video using
Google's Gemini image model (gemini-2.5-flash-image, "Nano Banana") for
top quality, driven by a detailed, story-accurate prompt. The Hindi
title is added afterwards as a crisp PIL text overlay (image models
render Hindi text unreliably). Falls back to the first scene image only
if Gemini is unavailable.
"""
import os
import time
import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from config import (
    GEMINI_API_KEY, GEMINI_IMAGE_MODEL, THUMB_WIDTH, THUMB_HEIGHT,
    GHIBLI_STYLE, NEGATIVE_STYLE, VIDEO_WIDTH, VIDEO_HEIGHT,
)
from utils import logger, ensure_dir, sanitize_filename


class ThumbnailGenerator:
    """Generates Gemini-powered Ghibli-style YouTube thumbnails."""

    def __init__(self, model_id: str = GEMINI_IMAGE_MODEL):
        self.model_id = model_id
        self.width = THUMB_WIDTH
        self.height = THUMB_HEIGHT
        self.max_retries = 3
        self.retry_delay = 6
        self._client = None

    def _get_client(self):
        """Lazily create the google-genai client (needs GEMINI_API_KEY)."""
        if self._client is not None:
            return self._client
        if not GEMINI_API_KEY:
            logger.error("  GEMINI_API_KEY not set — cannot generate thumbnail")
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"  Failed to init Gemini client: {e}")
            self._client = None
        return self._client

    def _query_api(self, prompt: str) -> Optional[bytes]:
        """
        Generate a thumbnail image with Gemini.
        Returns raw image bytes on success, None on failure.
        """
        client = self._get_client()
        if client is None:
            return None

        try:
            from google.genai import types
        except Exception:
            types = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"  Gemini thumbnail request "
                    f"(attempt {attempt}/{self.max_retries}, model={self.model_id})"
                )
                kwargs = {"model": self.model_id, "contents": prompt}
                if types is not None:
                    try:
                        kwargs["config"] = types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio="16:9"),
                        )
                    except Exception:
                        pass  # older SDK: omit config, still returns an image

                response = client.models.generate_content(**kwargs)

                # Extract the first inline image part from the response
                for cand in getattr(response, "candidates", None) or []:
                    content = getattr(cand, "content", None)
                    for part in getattr(content, "parts", None) or []:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            return inline.data

                logger.warning("  Gemini returned no image part")

            except Exception as e:
                logger.warning(
                    f"  Gemini thumbnail failed (attempt {attempt}): {e}"
                )

            time.sleep(self.retry_delay)

        logger.error("  All retries exhausted for Gemini thumbnail")
        return None

    def _add_title_overlay(
        self,
        image_path: str,
        title: str,
        output_path: str,
    ) -> str:
        """
        Overlay the story title text on the thumbnail image.
        Uses bold text with stroke and a semi-transparent gradient
        bar at the bottom for readability.
        """
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size

        # Create a gradient overlay at the bottom 35% of the image
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        gradient_height = int(height * 0.35)
        gradient_start = height - gradient_height

        for y in range(gradient_start, height):
            ratio = (y - gradient_start) / gradient_height
            alpha = int(180 * ratio)
            draw.line(
                [(0, y), (width, y)],
                fill=(0, 0, 0, alpha),
            )

        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

        # Draw the title text
        draw = ImageDraw.Draw(img)

        # Try to load a bold font
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ]
        font = None
        font_size = 56
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, font_size)
                break
        if font is None:
            font = ImageFont.load_default()

        # Word-wrap the title
        words = title.split()
        lines = []
        current_line = []
        max_width = width - 80  # padding

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

        # Limit to 3 lines max
        if len(lines) > 3:
            lines = lines[:3]

        # Calculate vertical position (centered in gradient area)
        line_height = font_size + 10
        total_text_height = len(lines) * line_height
        y_start = height - total_text_height - 40

        # Draw each line with stroke
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = y_start + (i * line_height)

            # Draw stroke (outline)
            for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
                draw.text(
                    (x + ox, y + oy), line,
                    fill=(0, 0, 0),
                    font=font,
                )

            # Draw main text
            draw.text((x, y), line, fill=(255, 255, 255), font=font)

        img.save(output_path, quality=95)
        return output_path

    def _create_fallback_thumbnail(
        self,
        title: str,
        scene_image_path: str,
        output_path: str,
    ) -> str:
        """
        If the Ghibli API fails, use the first scene's cartoon image
        as the thumbnail base and overlay the title.
        """
        if os.path.exists(scene_image_path):
            # Use the scene image, resized to 1280x720
            img = Image.open(scene_image_path).convert("RGBA")
            img = img.resize((1280, 720), Image.LANCZOS)
            temp_path = output_path.replace(".jpg", "_temp.png")
            img.convert("RGB").save(temp_path, quality=95)
            self._add_title_overlay(temp_path, title, output_path)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            # Solid color fallback
            img = Image.new("RGB", (1280, 720), (100, 150, 200))
            img.save(output_path, quality=95)
            self._add_title_overlay(output_path, title, output_path)

        logger.info("Fallback thumbnail created (Ghibli API unavailable)")
        return output_path

    def generate_thumbnail(
        self,
        title: str,
        story_summary: str,
        scene_image_path: str,
        job_dir: str,
    ) -> str:
        """
        Generate a Ghibli-style thumbnail for the story.
        Falls back to scene image if the API is unavailable.
        Returns path to the final thumbnail JPG (1280x720).
        """
        thumbnails_dir = os.path.join(job_dir, "thumbnails")
        ensure_dir(thumbnails_dir)
        output_path = os.path.join(thumbnails_dir, "thumbnail.jpg")
        raw_path = os.path.join(thumbnails_dir, "ghibli_raw.png")

        # Build a rich, story-accurate prompt for Gemini. We ask for a
        # clean lower-third (for the title overlay) and NO in-image text.
        ghibli_prompt = (
            f"{GHIBLI_STYLE}. "
            f"Create a stunning, eye-catching, high-click-through YouTube "
            f"thumbnail for a children's story video. "
            f"Story scene to depict: {story_summary}. "
            f"Show one clear, emotive main character as the focal point with an "
            f"expressive face, set in a magical storybook atmosphere. Use rich, "
            f"vibrant, saturated colors, dramatic soft cinematic lighting, strong "
            f"depth and fine detail, and a bold professional 16:9 composition. "
            f"Place the main subject toward one side and keep the lower-third area "
            f"visually clean and uncluttered so a title can be added there later. "
            f"Absolutely NO text, letters, words, numbers, captions, watermark or "
            f"logo anywhere in the image. Keep it wholesome, child-friendly and "
            f"non-violent. Avoid: {NEGATIVE_STYLE}."
        )

        logger.info(f"Generating Gemini Ghibli-style thumbnail ({self.model_id})...")
        image_bytes = self._query_api(ghibli_prompt)

        if image_bytes:
            with open(raw_path, "wb") as f:
                f.write(image_bytes)

            # Resize to 1280x720 if needed
            img = Image.open(raw_path).convert("RGB")
            if img.size != (1280, 720):
                img = img.resize((1280, 720), Image.LANCZOS)
                img.save(raw_path, quality=95)

            # Overlay title text
            self._add_title_overlay(raw_path, title, output_path)

            # Clean up raw image
            if os.path.exists(raw_path):
                os.remove(raw_path)

            logger.info(f"Ghibli thumbnail generated: {output_path}")
        else:
            logger.warning("Ghibli API failed, using fallback thumbnail")
            self._create_fallback_thumbnail(title, scene_image_path, output_path)

        return output_path
