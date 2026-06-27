"""
Text-to-Speech engine using edge-tts — Hindi female voice
(hi-IN-SwaraNeural) with per-scene emotion adjustments.

Emotion simulation via rate, pitch, and volume:
  happy     → +12% rate, +3Hz pitch, +0% volume
  excited   → +18% rate, +5Hz pitch, +5% volume
  sad       → -15% rate, -3Hz pitch, -5% volume
  scary     → -8% rate, -2Hz pitch, -10% volume
  tense     → -5% rate, +1Hz pitch, -5% volume
  mysterious→ -10% rate, -1Hz pitch, -8% volume
  peaceful  → -8% rate, +0Hz pitch, +0% volume
  neutral   → +0% rate, +0Hz pitch, +0% volume
"""
import asyncio
import os
import logging
from typing import Optional

import edge_tts

from config import DEFAULT_VOICE, OUTPUT_DIR
from utils import logger, chunk_text, ensure_dir

# Hindi voice options
VOICE_OPTIONS = {
    "narrator_female": "hi-IN-SwaraNeural",   # primary — female
    "narrator_male": "hi-IN-MadhurNeural",     # backup — male
}

# Emotion profiles: (rate, pitch, volume)
EMOTION_PROFILES = {
    "happy":       ("+12%", "+3Hz",  "+0%"),
    "excited":     ("+18%", "+5Hz",  "+5%"),
    "sad":         ("-15%", "-3Hz",  "-5%"),
    "scary":       ("-8%",  "-2Hz",  "-10%"),
    "tense":       ("-5%",  "+1Hz",  "-5%"),
    "mysterious":  ("-10%", "-1Hz",  "-8%"),
    "peaceful":    ("-8%",  "+0Hz",  "+0%"),
    "neutral":     ("+0%",  "+0Hz",  "+0%"),
}


class TTSEngine:
    """Hindi female TTS with emotion-aware narration."""

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    def _get_emotion_params(self, mood: str) -> tuple[str, str, str]:
        """Return (rate, pitch, volume) for a given mood."""
        return EMOTION_PROFILES.get(mood.lower(), EMOTION_PROFILES["neutral"])

    async def _generate_audio(
        self,
        text: str,
        output_path: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> bool:
        """Generate a single audio file from Hindi text."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
        )
        await communicate.save(output_path)
        return os.path.exists(output_path)

    async def _generate_subtitles(
        self,
        text: str,
        srt_path: str,
        offset_seconds: float = 0.0,
    ) -> bool:
        """Generate SRT subtitle file using edge-tts WordBoundary events."""
        word_boundaries = []
        communicate = edge_tts.Communicate(text, self.voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"],
                    "duration": chunk["duration"],
                })

        with open(srt_path, "w", encoding="utf-8") as f:
            for i, wb in enumerate(word_boundaries, 1):
                start_sec = (wb["offset"] / 10_000_000) + offset_seconds
                end_sec = start_sec + (wb["duration"] / 10_000_000)
                f.write(f"{i}\n")
                f.write(f"{self._format_srt_time(start_sec)} --> "
                        f"{self._format_srt_time(end_sec)}\n")
                f.write(f"{wb['text']}\n\n")

        return os.path.exists(srt_path)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_scene_audio(
        self,
        scene_index: int,
        narration: str,
        job_dir: str,
        mood: str = "neutral",
    ) -> dict:
        """
        Generate emotion-adjusted audio + subtitles for a single scene.
        The mood determines rate, pitch, and volume to simulate
        human-like emotional delivery in the Hindi female voice.
        """
        ensure_dir(job_dir)
        audio_path = os.path.join(job_dir, f"scene_{scene_index:03d}.mp3")
        srt_path = os.path.join(job_dir, f"scene_{scene_index:03d}.srt")

        # Get emotion parameters for this scene's mood
        rate, pitch, volume = self._get_emotion_params(mood)

        logger.info(
            f"  दृश्य {scene_index + 1}: भावना='{mood}' | "
            f"rate={rate} pitch={pitch} volume={volume}"
        )

        # Chunk long narration if needed
        chunks = chunk_text(narration, max_chars=3000)

        if len(chunks) == 1:
            asyncio.run(self._generate_audio(
                narration, audio_path, rate=rate, pitch=pitch, volume=volume
            ))
            asyncio.run(self._generate_subtitles(narration, srt_path))
        else:
            chunk_files = []
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(
                    job_dir, f"scene_{scene_index:03d}_chunk_{i}.mp3"
                )
                asyncio.run(self._generate_audio(
                    chunk, chunk_path, rate=rate, pitch=pitch, volume=volume
                ))
                chunk_files.append(chunk_path)

            concat_list = os.path.join(job_dir, f"scene_{scene_index:03d}_concat.txt")
            with open(concat_list, "w") as f:
                for cf in chunk_files:
                    f.write(f"file '{cf}'\n")

            os.system(
                f"ffmpeg -y -f concat -safe 0 -i '{concat_list}' "
                f"-c copy '{audio_path}' 2>/dev/null"
            )

            asyncio.run(self._generate_subtitles(narration, srt_path))

            for cf in chunk_files:
                if os.path.exists(cf):
                    os.remove(cf)
            if os.path.exists(concat_list):
                os.remove(concat_list)

        logger.info(f"  दृश्य {scene_index + 1}: ऑडियो + उपशीर्षक तैयार")

        return {
            "audio_path": audio_path,
            "srt_path": srt_path,
            "scene_index": scene_index,
            "mood": mood,
        }

    def generate_full_narration(
        self,
        scenes: list[dict],
        job_dir: str,
    ) -> list[dict]:
        """Generate emotion-adjusted audio for all scenes."""
        results = []
        for i, scene in enumerate(scenes):
            result = self.generate_scene_audio(
                scene_index=i,
                narration=scene["narration"],
                job_dir=job_dir,
                mood=scene.get("mood", "neutral"),
            )
            results.append(result)

        logger.info(f"{len(results)} दृश्यों के लिए भावनात्मक ऑडियो तैयार")
        return results
