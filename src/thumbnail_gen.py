"""
Ghibli-style thumbnail generator.
Creates an eye-catching YouTube thumbnail for each story video using
the Hugging Face Inference API with a Ghibli-style fine-tuned model.
Overlays the story title text for maximum click-through appeal.
"""
import os
import time
import logging
import requests
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from config import HUGGINGFACE_API_KEY, HF_GHIBLI_MODEL, VIDEO_WIDTH, VIDEO_HEIGHT
from utils import logger, ensure_dir, sanitize_filename

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"

# Negative prompt to keep thumbnails clean and appealing
THUMBNAIL_NEGATIVE_PROMPT = (
    "nsfw, nude, explicit, gore, violence, blood, "
    "blurry, low quality, distorted, deformed, "
    "text, watermark, signature, ugly, bad anatomy"
)


class ThumbnailGenerator:
    """Generates Ghibli-style YouTube thumbnails with title overlay."""

    def __init__(self, model_id: str = HF_GHIBLI_MODEL):
        self.model_id = model_id
        self.api_url = HF_INFERENCE_URL.format(model=model_id)
        self.headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        self.max_retries = 4
        self.retry_delay = 10

    def _query_api(self, prompt: str) -> Optional[bytes]:
        """Send a text-to-image request to the HF Inference API."""
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": THUMBNAIL_NEGATIVE_PROMPT,
                "num_inference_steps": 35,
                "guidance_scale": 8.0,
                "width": 1280,
                "height": 720,  # 16:9 YouTube thumbnail
            },
            "options": {"wait_for_model": True},
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )

                if response.status_code == 503:
                    est = response.json().get("estimated_time", 20)
                    logger.info(f"  Thumbnail model loading, waiting {est}s...")
                    time.sleep(max(est, self.retry_delay))
                    continue

                if response.status_code == 429:
                    wait = int(response.headers.get("Retry-After", self.retry_delay))
                    logger.warning(f"  Rate limited, waiting {wait}s")
                    time.sleep(wait)
                    continue

                if response.status_code == 200:
                    return response.content

                logger.error(
                    f"  Thumbnail API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                time.sleep(self.retry_delay)

            except requests.RequestException as e:
                logger.warning(f"  Thumbnail request failed (attempt {attempt}): {e}")
                time.sleep(self.retry_delay)

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

        # Build a Ghibli-style prompt from the story summary
        ghibli_prompt = (
            f"Studio Ghibli style anime illustration, {story_summary}, "
            f"beautiful soft lighting, lush nature, whimsical, "
            f"hand-painted look, vibrant colors, cinematic composition, "
            f"highly detailed, masterpiece quality"
        )

        logger.info("Generating Ghibli-style thumbnail...")
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
