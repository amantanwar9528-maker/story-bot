"""
Cartoon-style image generation using the Hugging Face Inference API.
Generates one illustration per scene based on the visual_prompt from
the script. Includes retry logic, rate-limit handling, and a local
fallback so the pipeline never deadlocks if the API is overloaded.
"""
import os
import time
import logging
import requests
from typing import Optional
from PIL import Image, ImageFilter, ImageEnhance

from config import HUGGINGFACE_API_KEY, HF_CARTOON_MODEL, OUTPUT_DIR
from utils import logger, ensure_dir, sanitize_filename

# Hugging Face Inference API endpoint
HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"

# Negative prompt to keep images child-safe and high quality
NEGATIVE_PROMPT = (
    "nsfw, nude, naked, explicit, gore, blood, violence, "
    "realistic, photorealistic, photograph, 3d render, "
    "blurry, low quality, distorted, deformed, ugly, "
    "extra fingers, bad anatomy, watermark, text, signature"
)


class ImageGenerator:
    """Generates cartoon-style scene illustrations via Hugging Face."""

    def __init__(self, model_id: str = HF_CARTOON_MODEL):
        self.model_id = model_id
        self.api_url = HF_INFERENCE_URL.format(model=model_id)
        self.headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        self.max_retries = 4
        self.retry_delay = 10  # seconds between retries

    def _query_api(self, prompt: str) -> Optional[bytes]:
        """
        Send a text-to-image request to the HF Inference API.
        Returns raw image bytes on success, None on failure.
        """
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": NEGATIVE_PROMPT,
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": 1024,
                "height": 576,  # 16:9 aspect ratio for video
            },
            "options": {"wait_for_model": True},
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"  HF image request (attempt {attempt}/{self.max_retries})"
                )
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=90,
                )

                # Model loading — wait and retry
                if response.status_code == 503:
                    estimated_time = response.json().get("estimated_time", 20)
                    logger.info(
                        f"  Model loading, waiting {estimated_time}s..."
                    )
                    time.sleep(max(estimated_time, self.retry_delay))
                    continue

                # Rate limited
                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", self.retry_delay)
                    )
                    logger.warning(f"  Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 200:
                    return response.content

                logger.error(
                    f"  HF API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                time.sleep(self.retry_delay)

            except requests.exceptions.Timeout:
                logger.warning(f"  Request timed out on attempt {attempt}")
                time.sleep(self.retry_delay)
            except requests.exceptions.RequestException as e:
                logger.warning(f"  Request failed on attempt {attempt}: {e}")
                time.sleep(self.retry_delay)

        logger.error("  All retries exhausted for image generation")
        return None

    def _create_fallback_image(
        self, prompt: str, output_path: str, scene_index: int
    ) -> str:
        """
        Generate a simple gradient placeholder with scene text if the
        API fails entirely. Ensures the pipeline never stalls.
        """
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1024, 576
        # Create a pleasant gradient background
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # Color palette for children's content
        palettes = [
            ((135, 206, 235), (70, 130, 180)),   # sky blue
            ((255, 182, 193), (255, 105, 180)),  # pink
            ((144, 238, 144), (34, 139, 34)),    # green
            ((255, 218, 185), (255, 140, 0)),    # orange
            ((221, 160, 221), (138, 43, 226)),   # purple
        ]
        c1, c2 = palettes[scene_index % len(palettes)]

        for y in range(height):
            ratio = y / height
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add scene number
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

        text = f"Scene {scene_index + 1}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(
            ((width - text_w) // 2, (height - text_h) // 2),
            text,
            fill="white",
            font=font,
            stroke_width=2,
            stroke_fill="black",
        )

        img.save(output_path)
        logger.info(f"  Fallback image created for scene {scene_index + 1}")
        return output_path

    def _post_process(self, image_path: str) -> str:
        """
        Enhance the generated image: sharpen, boost saturation,
        and ensure it fits the target video resolution.
        """
        img = Image.open(image_path).convert("RGB")

        # Resize to fit 1920x1080 with padding if needed
        target_w, target_h = 1920, 1080
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h

        if img_ratio > target_ratio:
            new_h = target_h
            new_w = int(target_h * img_ratio)
        else:
            new_w = target_w
            new_h = int(target_w / img_ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center-crop or pad to exact target
        if new_w > target_w:
            left = (new_w - target_w) // 2
            img = img.crop((left, 0, left + target_w, target_h))
        elif new_h > target_h:
            top = (new_h - target_h) // 2
            img = img.crop((0, top, target_w, top + target_h))
        else:
            # Pad with black bars
            canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
            offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
            canvas.paste(img, offset)
            img = canvas

        # Enhance
        img = ImageEnhance.Color(img).enhance(1.15)   # boost saturation
        img = ImageEnhance.Sharpness(img).enhance(1.3)  # sharpen
        img = ImageEnhance.Contrast(img).enhance(1.05)

        img.save(image_path, quality=95)
        return image_path

    def generate_scene_image(
        self,
        scene_index: int,
        visual_prompt: str,
        job_dir: str,
    ) -> str:
        """
        Generate a single cartoon illustration for a scene.
        Returns the path to the saved image file.
        """
        ensure_dir(job_dir)
        image_path = os.path.join(job_dir, f"scene_{scene_index:03d}.png")

        # Prepend style keywords to enforce cartoon look
        full_prompt = (
            f"cartoon style, children's book illustration, vibrant colors, "
            f"soft shading, friendly characters, {visual_prompt}"
        )

        image_bytes = self._query_api(full_prompt)

        if image_bytes:
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            self._post_process(image_path)
            logger.info(f"  Scene {scene_index + 1}: cartoon image generated")
        else:
            logger.warning(
                f"  Scene {scene_index + 1}: API failed, using fallback"
            )
            self._create_fallback_image(visual_prompt, image_path, scene_index)

        return image_path

    def generate_all_images(
        self,
        scenes: list[dict],
        job_dir: str,
    ) -> list[str]:
        """
        Generate images for all scenes sequentially.
        Rate-limits itself to avoid hitting HF free-tier caps.
        Returns list of image file paths.
        """
        image_paths = []
        images_dir = os.path.join(job_dir, "images")
        ensure_dir(images_dir)

        total = len(scenes)
        for i, scene in enumerate(scenes):
            logger.info(f"Generating image {i + 1}/{total}")
            path = self.generate_scene_image(
                scene_index=i,
                visual_prompt=scene.get("visual_prompt", ""),
                job_dir=images_dir,
            )
            image_paths.append(path)
            # Rate limit: 2-second pause between requests
            if i < total - 1:
                time.sleep(2)

        logger.info(f"Generated {len(image_paths)} scene images")
        return image_paths
