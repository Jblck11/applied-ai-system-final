"""Command line runner for the Music Recommender Simulation.

Run from the repository root with:

    python -m src.main

The CLI is a thin layer: it loads the catalog, configures logging, and hands a
user taste profile to the guarded pipeline in ``pipeline.run_recommendation``.
All scoring, validation, confidence, and self-critique logic lives in the
``recommender`` and ``reliability`` modules.
"""

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


def main() -> None:
    logger = configure_logging(logfile=_project_path("logs", "run.log"))

    csv_path = _project_path("data", "songs.csv")
    songs = load_songs(csv_path)
    logger.info("LOAD: %d songs from %s", len(songs), os.path.relpath(csv_path, os.getcwd()) if os.path.isabs(csv_path) else csv_path)

    user_prefs = {
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    }

    try:
        result = run_recommendation(user_prefs, songs, k=5)
    except RecommenderInputError as exc:
        logger.error("Input rejected: %s", exc)
        print(f"\nCould not produce recommendations: {exc}")
        return

    recommendations = result["recommendations"]
    skipped = result["skipped"]

    print(f"\nLoaded songs: {result['catalog_size']} usable"
          + (f" ({len(skipped)} skipped)" if skipped else ""))
    print("\nTop recommendations:\n")
    for item in recommendations:
        song = item["song"]
        print(f"{song['title']:<24} | Score: {item['score']:>5.2f} | {item['explanation']}")


if __name__ == "__main__":
    main()
