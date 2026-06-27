#!/usr/bin/env python3
"""
Story Bot — Fully Automated YouTube Children's Story Channel
Free tools only. No paid APIs. Generates & uploads 3 videos/day.

Usage:
    python main.py                          # Local scheduler (7AM, 1PM, 6PM)
    python main.py --run-now                # Run full daily pipeline now (3 videos)
    python main.py --run-now --num-videos 1
    python main.py --run-now --genre horror # Make a single test video of one genre

NOTE:
    In production you do NOT need this scheduler running. GitHub Actions
    (.github/workflows/generate-and-upload.yml) triggers the pipeline on a
    cron schedule, so your laptop can stay off. This local scheduler is only
    for testing or running on an always-on machine.
"""
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# The src modules use flat imports like `from config import ...`,
# so the src/ directory must be on sys.path.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def run_now(num_videos: int, genre: str | None) -> None:
    """Run the pipeline immediately."""
    from content_manager import ContentManager
    manager = ContentManager()

    if genre:
        # Single-video test run for one specific genre.
        print(f"Running single-video test (genre={genre})...\n")
        topics = manager.script_writer.generate_unique_topics(
            used_topics=manager._get_used_topics(),
            count=1,
            topic_type=genre,
        )
        if not topics:
            print("Could not generate a topic. Check GEMINI_API_KEY.")
            return
        topic = topics[0]
        topic["type"] = genre
        date_str = datetime.now().strftime("%Y-%m-%d")
        result = manager._process_single_video(topic=topic, slot=0, date_str=date_str)
        print(f"\nResult: {result}")
    else:
        print(f"Running full daily pipeline ({num_videos} videos)...\n")
        manager.run_daily_pipeline(num_videos=num_videos)


def run_scheduler(num_videos: int) -> None:
    """
    Lightweight, dependency-free local scheduler.

    Fires the full daily pipeline once per day at the first configured
    upload time. The pipeline schedules each video's public publish time
    (7 AM / 1 PM / 6 PM) on YouTube via the `publish_at` field, so all
    three videos can be generated in one batch.
    """
    from config import UPLOAD_TIMES
    from content_manager import ContentManager

    trigger_time = UPLOAD_TIMES[0] if UPLOAD_TIMES else "07:00"
    print("Story Bot local scheduler started.")
    print(f"  Daily trigger time : {trigger_time}")
    print(f"  Publish slots      : {', '.join(UPLOAD_TIMES)}")
    print("  (Production scheduling is handled by GitHub Actions.)\n")
    print("Waiting for trigger time... (Ctrl+C to stop)")

    last_run_date = None
    try:
        while True:
            now = datetime.now()
            current_hhmm = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")
            if current_hhmm == trigger_time and last_run_date != today:
                last_run_date = today
                print(f"\n[{now.isoformat(timespec='seconds')}] Triggering daily pipeline...")
                try:
                    ContentManager().run_daily_pipeline(num_videos=num_videos)
                except Exception as e:  # keep the scheduler alive on failure
                    print(f"Pipeline run failed: {e}")
            time.sleep(20)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated YouTube Story Channel Bot"
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="Run the pipeline immediately instead of scheduling",
    )
    parser.add_argument(
        "--num-videos", type=int, default=3,
        help="Number of videos to generate in a daily run (default: 3)",
    )
    parser.add_argument(
        "--genre", choices=["children", "horror"], default=None,
        help="Generate a single test video of this genre (use with --run-now)",
    )
    args = parser.parse_args()

    if args.run_now:
        run_now(num_videos=args.num_videos, genre=args.genre)
    else:
        run_scheduler(num_videos=args.num_videos)


if __name__ == "__main__":
    main()
