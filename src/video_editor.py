"""
Core video assembly engine using FFmpeg directly (not MoviePy) for
maximum rendering speed on GitHub Actions' 2-core runners.

Pipeline per scene:
  1. Take the cartoon image (or stock video) as the visual base
  2. Apply Ken Burns zoom/pan effect for motion
  3. Overlay the narration audio
  4. Add subtitle text burn-in
  5. Add transition (fade/crossfade) between scenes

Final assembly:
  6. Concatenate all scene clips with transitions
  7. Mix in background music (ducked under narration)
  8. Add channel watermark/logo overlay
  9. Export final MP4 at 1920x1080, 30fps, H.264 + AAC
"""
import os
import json
import subprocess
import logging
from typing import Optional

from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, OUTPUT_DIR, OVERLAYS_DIR
from utils import logger, ensure_dir


class VideoEditor:
    """Assembles final video from images, audio, subtitles, and music."""

    def __init__(self):
        self.width = VIDEO_WIDTH
        self.height = VIDEO_HEIGHT
        self.fps = FPS

    def _run_ffmpeg(self, args: list[str], desc: str = "FFmpeg"):
        """Run an FFmpeg command and check for errors."""
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
        logger.info(f"  {desc}: running FFmpeg ({len(args)} args)")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"  FFmpeg error: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg failed during: {desc}")
        return result

    def _get_duration(self, media_path: str) -> float:
        """Get duration of a media file in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            media_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
        return 0.0

    def _is_valid_video(self, path: Optional[str]) -> bool:
        """True only if the file exists, is non-trivial, and has duration."""
        if not path or not os.path.exists(path) or os.path.getsize(path) < 1024:
            return False
        return self._get_duration(path) > 0.1

    def _subtitle_filter(self, srt_path: Optional[str]) -> str:
        """
        Build the subtitles burn-in filter, but only if the SRT exists
        and actually has content. An empty/missing SRT makes FFmpeg fail
        with 'Invalid data found when processing input', so we skip it.
        """
        if (not srt_path or not os.path.exists(srt_path)
                or os.path.getsize(srt_path) < 10):
            return ""
        escaped_srt = (
            srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        )
        return (
            f",subtitles='{escaped_srt}':force_style='FontName=Arial,"
            f"FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=40'"
        )

    def _create_scene_clip_from_image(
        self,
        image_path: str,
        audio_path: str,
        srt_path: str,
        scene_index: int,
        job_dir: str,
        zoom_direction: str = "in",
    ) -> str:
        """
        Create a video clip from a static image with:
        - Ken Burns zoom effect
        - Narration audio
        - Burned-in subtitles
        """
        clip_path = os.path.join(job_dir, f"clip_{scene_index:03d}.mp4")
        duration = self._get_duration(audio_path)

        if duration == 0:
            duration = 10  # fallback
            logger.warning(f"  Scene {scene_index}: no audio duration, using 10s")

        # Ken Burns zoom filter
        # zoompan needs frame count and works in output pixel space
        total_frames = int(duration * self.fps)

        if zoom_direction == "in":
            # Slow zoom in
            zoom_filter = (
                f"scale={self.width * 2}:{self.height * 2},"
                f"zoompan=z='min(zoom+0.0008,1.3)':"
                f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"
            )
        elif zoom_direction == "out":
            # Slow zoom out
            zoom_filter = (
                f"scale={self.width * 2}:{self.height * 2},"
                f"zoompan=z='if(eq(on,0),1.3,max(zoom-0.0008,1.0))':"
                f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"
            )
        else:
            # Pan left to right
            zoom_filter = (
                f"scale={self.width * 2}:{self.height * 2},"
                f"zoompan=z=1.2:x='iw-(iw/zoom)*on/{total_frames}':"
                f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"
            )

        # Subtitle burn-in (safe: empty/missing SRT is skipped)
        subtitle_filter = self._subtitle_filter(srt_path)

        def _build_and_run(sub: str):
            vf = f"{zoom_filter}{sub}"
            args = [
                "-loop", "1", "-i", image_path,       # input: image
                "-i", audio_path,                       # input: audio
                "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(duration),
                "-r", str(self.fps),
                clip_path,
            ]
            self._run_ffmpeg(args, f"Scene {scene_index} clip creation")

        try:
            _build_and_run(subtitle_filter)
        except RuntimeError:
            if subtitle_filter:
                logger.warning(
                    f"  Scene {scene_index}: subtitle burn-in failed, "
                    f"retrying without subtitles"
                )
                _build_and_run("")
            else:
                raise
        return clip_path

    def _create_scene_clip_from_video(
        self,
        video_path: str,
        audio_path: str,
        srt_path: str,
        scene_index: int,
        job_dir: str,
    ) -> str:
        """Create a video clip from a stock video with narration audio."""
        clip_path = os.path.join(job_dir, f"clip_{scene_index:03d}.mp4")

        # Validate the stock video before handing it to FFmpeg. A corrupt
        # or 0-byte download causes 'Invalid data found when processing
        # input'; raising here lets the caller fall back to the image.
        if not self._is_valid_video(video_path):
            raise RuntimeError(
                f"Invalid/empty stock video for scene {scene_index}: {video_path}"
            )

        audio_duration = self._get_duration(audio_path)
        if audio_duration == 0:
            audio_duration = 10

        # Subtitle filter (safe: empty/missing SRT is skipped)
        subtitle_filter = self._subtitle_filter(srt_path)

        def _build_and_run(sub: str):
            vf = (
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black"
                f"{sub}"
            )
            args = [
                "-i", video_path,           # input: stock video
                "-i", audio_path,            # input: narration audio
                "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(audio_duration),
                "-r", str(self.fps),
                clip_path,
            ]
            self._run_ffmpeg(args, f"Scene {scene_index} video clip")

        try:
            _build_and_run(subtitle_filter)
        except RuntimeError:
            if subtitle_filter:
                logger.warning(
                    f"  Scene {scene_index}: subtitle burn-in failed, "
                    f"retrying without subtitles"
                )
                _build_and_run("")
            else:
                raise
        return clip_path

    def _add_transition(
        self,
        clip_paths: list[str],
        job_dir: str,
        transition_type: str = "fade",
    ) -> str:
        """
        Concatenate clips with crossfade transitions between them.
        Uses FFmpeg's xfade filter for smooth transitions.
        """
        if len(clip_paths) == 1:
            return clip_paths[0]

        output_path = os.path.join(job_dir, "assembled_no_music.mp4")

        # Build input args
        input_args = []
        for p in clip_paths:
            input_args.extend(["-i", p])

        # Build filter complex for xfade chain
        # xfade transitions: fade, dissolve, wipeleft, slideup, circleopen
        transition_map = {
            "fade": "fade",
            "dissolve": "dissolve",
            "wipe": "wipeleft",
            "slide": "slideup",
            "circle": "circleopen",
        }
        xfade_type = transition_map.get(transition_type, "fade")
        transition_duration = 0.5  # seconds

        # Get durations for offset calculation
        filter_parts = []
        prev_label = "[0:v]"
        offset = 0.0

        for i in range(1, len(clip_paths)):
            prev_duration = self._get_duration(clip_paths[i - 1])
            offset += prev_duration - transition_duration

            current_label = f"[{i}:v]"
            output_label = f"[v{i}]" if i < len(clip_paths) - 1 else "[vout]"

            filter_parts.append(
                f"{prev_label}{current_label}xfade=transition={xfade_type}:"
                f"duration={transition_duration}:offset={offset}{output_label}"
            )
            prev_label = output_label

        # Audio: simple concat with short crossfade
        audio_filter_parts = []
        prev_a_label = "[0:a]"
        a_offset = 0.0
        for i in range(1, len(clip_paths)):
            prev_duration = self._get_duration(clip_paths[i - 1])
            a_offset += prev_duration - transition_duration
            current_a_label = f"[{i}:a]"
            output_a_label = f"[a{i}]" if i < len(clip_paths) - 1 else "[aout]"
            audio_filter_parts.append(
                f"{prev_a_label}{current_a_label}acrossfade=d={transition_duration}{output_a_label}"
            )
            prev_a_label = output_a_label

        filter_complex = ";".join(filter_parts + audio_filter_parts)

        args = input_args + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", str(self.fps),
            output_path,
        ]

        self._run_ffmpeg(args, "Transition assembly")
        return output_path

    def _mix_background_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        music_volume: float = 0.15,
    ) -> str:
        """
        Mix background music under the narration audio.
        Music is looped to match video duration and ducked (lowered)
        so narration is always clearly audible.
        """
        video_duration = self._get_duration(video_path)

        args = [
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            # Loop music to full duration, lower its volume, mix with existing audio
            f"[1:a]aloop=loop=-1:size=2e9,atrim=duration={video_duration},"
            f"volume={music_volume}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]

        self._run_ffmpeg(args, "Background music mixing")
        return output_path

    def _add_watermark(self, video_path: str, output_path: str) -> str:
        """Add a channel logo/watermark in the bottom-right corner."""
        logo_path = os.path.join(OVERLAYS_DIR, "watermark.png")
        if not os.path.exists(logo_path):
            logger.info("No watermark found, skipping overlay")
            return video_path

        args = [
            "-i", video_path,
            "-i", logo_path,
            "-filter_complex",
            f"[1:v]scale=120:-1[wm];[0:v][wm]overlay=W-w-30:H-h-30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            output_path,
        ]

        self._run_ffmpeg(args, "Watermark overlay")
        return output_path

    def assemble_video(
        self,
        scenes: list[dict],
        scene_assets: list[dict],
        music_path: Optional[str],
        job_dir: str,
        video_title: str = "story",
    ) -> str:
        """
        Full assembly pipeline:
        1. Create per-scene clips (image or video based)
        2. Concatenate with transitions
        3. Mix background music
        4. Add watermark
        5. Return final video path
        """
        clips_dir = os.path.join(job_dir, "clips")
        ensure_dir(clips_dir)

        # ── Step 1: Create scene clips ──
        clip_paths = []
        zoom_directions = ["in", "out", "left"]

        for i, (scene, assets) in enumerate(zip(scenes, scene_assets)):
            logger.info(f"Rendering scene {i + 1}/{len(scenes)}")

            # Only keep stock videos that are actually valid files.
            stock_videos = [
                v for v in assets.get("stock_videos", [])
                if self._is_valid_video(v)
            ]
            image_path = assets.get("image_path")
            clip = None

            # 1) Try stock video (if any valid one)
            if stock_videos:
                try:
                    clip = self._create_scene_clip_from_video(
                        video_path=stock_videos[0],
                        audio_path=assets["audio_path"],
                        srt_path=assets["srt_path"],
                        scene_index=i,
                        job_dir=clips_dir,
                    )
                except Exception as e:
                    logger.warning(
                        f"  Scene {i}: stock video failed ({e}); "
                        f"falling back to image"
                    )
                    clip = None

            # 2) Fall back to the cartoon image
            if clip is None and image_path and os.path.exists(image_path):
                zoom_dir = zoom_directions[i % 3]
                try:
                    clip = self._create_scene_clip_from_image(
                        image_path=image_path,
                        audio_path=assets["audio_path"],
                        srt_path=assets["srt_path"],
                        scene_index=i,
                        job_dir=clips_dir,
                        zoom_direction=zoom_dir,
                    )
                except Exception as e:
                    logger.error(f"  Scene {i}: image clip failed ({e}); skipping scene")
                    clip = None

            if clip:
                clip_paths.append(clip)
            else:
                logger.error(f"  Scene {i}: no usable clip, skipping")

        if not clip_paths:
            raise RuntimeError("No clips were created — cannot assemble video")

        # ── Step 2: Concatenate with transitions ──
        logger.info("Concatenating scenes with transitions...")
        assembled = self._add_transition(
            clip_paths, job_dir, transition_type="fade"
        )

        # ── Step 3: Mix background music ──
        if music_path:
            logger.info("Mixing background music...")
            with_music = os.path.join(job_dir, "with_music.mp4")
            assembled = self._mix_background_music(
                assembled, music_path, with_music, music_volume=0.12
            )

        # ── Step 4: Add watermark ──
        logger.info("Adding watermark...")
        final_path = os.path.join(job_dir, f"{video_title}_final.mp4")
        final_path = self._add_watermark(assembled, final_path)

        # Log final video info
        final_duration = self._get_duration(final_path)
        file_size = os.path.getsize(final_path) / (1024 * 1024)
        logger.info(
            f"Final video: {final_path} | "
            f"Duration: {final_duration:.0f}s ({final_duration/60:.1f} min) | "
            f"Size: {file_size:.1f} MB"
        )

        return final_path

    def create_instagram_reel(
        self,
        full_video_path: str,
        job_dir: str,
        reel_duration: int = 30,
    ) -> str:
        """
        Extract a short promotional clip from the full video for
        Instagram Reels. Crops to 9:16 vertical format (1080x1920)
        and selects the most visually interesting segment.
        """
        reel_dir = os.path.join(job_dir, "reels")
        ensure_dir(reel_dir)
        reel_path = os.path.join(reel_dir, "promo_reel.mp4")

        total_duration = self._get_duration(full_video_path)

        # Select a segment from the middle of the video (often most interesting)
        start_time = max(0, (total_duration / 2) - (reel_duration / 2))

        # Crop to vertical 9:16 (center crop) and resize to 1080x1920
        args = [
            "-ss", str(start_time),
            "-i", full_video_path,
            "-t", str(reel_duration),
            "-filter_complex",
            # Crop center to 9:16 aspect, then scale
            f"crop=ih*9/16:ih,scale=1080:1920:flags=lanczos,"
            # Add subtle fade in/out
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={reel_duration-0.5}:d=0.5[v];"
            f"[0:a]afade=t=in:st=0:d=0.5,afade=t=out:st={reel_duration-0.5}:d=0.5[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-r", "30",
            reel_path,
        ]

        self._run_ffmpeg(args, "Instagram Reel creation")
        logger.info(f"Instagram Reel created: {reel_path} ({reel_duration}s)")
        return reel_path
