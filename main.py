#!/usr/bin/env python3
"""
Story Bot — Fully Automated YouTube Children's Story Channel
Free tools only. No paid APIs. Runs 3 uploads/day.

Usage:
    python main.py              # Start scheduled bot (7AM, 1PM, 6PM)
    python main.py --run-now    # Run pipeline immediately (test)
    python main.py --run-now --genre horror  # Test with horror genre
"""
import sys
import argparse
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(
        description="Automated YouTube Story Channel Bot"
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="Run the pipeline immediately instead of scheduling"
    )
    parser.add_argument(
        "--genre", choices=["children", "horror"], default=None,
        help="Story genre to use"
    )
    args = parser.parse_args()

    if args.run_now:
        # Immediate test run
        from src.pipeline.orchestrator import PipelineOrchestrator
        print("Running pipeline immediately (test mode)...\n")
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run_full_pipeline(genre=args.genre)
        print(f"\nResult: {result}")
    else:
        # Start scheduled bot
        from src.scheduler.task_scheduler import TaskScheduler
        bot = TaskScheduler()
        bot.run()


if __name__ == "__main__":
    main()
