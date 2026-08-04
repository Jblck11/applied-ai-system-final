"""Command line runner for the Music Recommender Simulation.

Run from the repository root with:

    python -m src.main

The CLI is a thin layer: it loads the catalog, configures logging, and hands a
user taste profile to the guarded pipeline in ``pipeline.run_recommendation``.
All scoring, validation, confidence, and self-critique logic lives in the
``recommender`` and ``reliability`` modules.
"""

import argparse
import os

try:  # package-style import (python -m src.main)
    from .recommender import load_songs
    from .pipeline import run_recommendation
    from .reliability import RecommenderInputError
    from .logging_setup import configure_logging
except ImportError:  # pragma: no cover - fallback for direct script execution
    from recommender import load_songs
    from pipeline import run_recommendation
    from reliability import RecommenderInputError
    from logging_setup import configure_logging


def _project_path(*parts: str) -> str:
    """Resolve a path relative to the project root, regardless of the current
    working directory, so ``data/songs.csv`` is always found."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, *parts)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Music recommender with confidence scoring and self-critique."
    )
    parser.add_argument("--genre", default="pop", help="favorite genre (default: pop)")
    parser.add_argument("--mood", default="happy", help="favorite mood (default: happy)")
    parser.add_argument("--energy", type=float, default=0.8,
                        help="target energy 0-1 (default: 0.8)")
    parser.add_argument("--acoustic", action="store_true",
                        help="prefer acoustic tracks")
    parser.add_argument("-k", type=int, default=5,
                        help="number of recommendations (default: 5)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logger = configure_logging(logfile=_project_path("logs", "run.log"))

    csv_path = _project_path("data", "songs.csv")
    songs = load_songs(csv_path)
    logger.info("LOAD: %d songs from %s", len(songs), os.path.relpath(csv_path, os.getcwd()) if os.path.isabs(csv_path) else csv_path)

    user_prefs = {
        "favorite_genre": args.genre,
        "favorite_mood": args.mood,
        "target_energy": args.energy,
        "likes_acoustic": args.acoustic,
    }

    try:
        result = run_recommendation(user_prefs, songs, k=args.k)
    except RecommenderInputError as exc:
        logger.error("Input rejected: %s", exc)
        print(f"\nCould not produce recommendations: {exc}")
        return

    recommendations = result["recommendations"]
    skipped = result["skipped"]

    print(f"\nLoaded songs: {result['catalog_size']} usable"
          + (f" ({len(skipped)} skipped)" if skipped else ""))
    print("\nTop recommendations:\n")
    flagged = 0
    for item in recommendations:
        song = item["song"]
        conf = item["confidence"]
        label = item["confidence_label"]
        flag = "  REVIEW" if item["needs_review"] else ""
        if item["needs_review"]:
            flagged += 1
        print(
            f"{song['title']:<24} | Score: {item['score']:>5.2f} "
            f"| Confidence: {conf:>4.2f} ({label:<6}){flag:<8} | {item['explanation']}"
        )
        if item["needs_review"]:
            print(f"{'':<24}   -> flagged for review: {'; '.join(item['critique']['review_reasons'])}")

    print(
        f"\nSelf-critique: {len(recommendations) - flagged}/{len(recommendations)} "
        f"recommendation(s) verified and trusted; {flagged} flagged for human review."
    )


if __name__ == "__main__":
    main()
