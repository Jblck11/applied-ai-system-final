"""Orchestration layer that ties the system together.

``run_recommendation`` is the single entry point the CLI and the evaluation
harness both call. It runs the pipeline in explicit, logged stages:

    validate input -> validate catalog -> score & rank -> package results

Later commits extend the per-recommendation packaging with a confidence score
and a self-critique verdict. Keeping all of that behind this one function is
what makes the AI feature *integrated* rather than a standalone script: every
consumer of the recommender goes through the same guarded, logged path.
"""

from typing import Any, Dict, List

try:  # package-style import (python -m src.main)
    from .recommender import recommend_songs
    from .reliability import RecommenderInputError, validate_songs, validate_user_prefs
    from .logging_setup import get_logger
except ImportError:  # pragma: no cover - fallback for direct script execution
    from recommender import recommend_songs
    from reliability import RecommenderInputError, validate_songs, validate_user_prefs
    from logging_setup import get_logger


def run_recommendation(user_prefs: Dict[str, Any], songs: List[Dict], k: int = 5) -> Dict[str, Any]:
    """Run the full guarded recommendation pipeline.

    Args:
        user_prefs: The user's taste profile.
        songs: The song catalog (list of dict records from ``load_songs``).
        k: How many recommendations to return.

    Returns:
        A dict with:
          - ``recommendations``: list of per-song result dicts
            (``song``, ``score``, ``explanation``).
          - ``skipped``: quarantined songs and the reason each was dropped.
          - ``catalog_size``: number of songs that passed validation.

    Raises:
        RecommenderInputError: if the profile or catalog is unusable. Callers
        are expected to catch this and report it cleanly.
    """
    logger = get_logger()
    logger.info("PLAN: validate -> score -> rank -> return top %d", k)

    validate_user_prefs(user_prefs)
    logger.info("VALIDATE-INPUT: user profile accepted.")

    valid_songs, skipped = validate_songs(songs)
    if skipped:
        logger.warning(
            "VALIDATE-CATALOG: quarantined %d bad song(s): %s",
            len(skipped),
            "; ".join(f"{s['song'].get('title', '?')} ({s['reason']})" for s in skipped),
        )
    logger.info("VALIDATE-CATALOG: %d song(s) usable.", len(valid_songs))

    ranked = recommend_songs(user_prefs, valid_songs, k=k)
    logger.info("RANK: produced %d recommendation(s).", len(ranked))

    recommendations: List[Dict[str, Any]] = []
    for song, score, explanation in ranked:
        recommendations.append(
            {
                "song": song,
                "score": score,
                "explanation": explanation,
            }
        )

    return {
        "recommendations": recommendations,
        "skipped": skipped,
        "catalog_size": len(valid_songs),
    }
