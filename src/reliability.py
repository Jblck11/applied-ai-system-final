"""Reliability layer for the recommender.

This module is the heart of the final-project extension. It adds three things
the original Module-3 recommender did not have:

1. **Input validation (guardrails)** - reject or quarantine malformed input
   before it can reach the scoring logic (this commit).
2. **Confidence scoring** - rate how sure the system is about each pick
   (added in a later commit).
3. **Self-critique / validation** - check each explanation's claims against the
   raw data and flag anything that cannot be verified (added in a later commit).

Everything here is deterministic and fully offline: the same input always
produces the same output, which is what makes the system reproducible.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

try:  # weights live with the scoring rule; import them so confidence stays in sync
    from .recommender import (
        ACOUSTIC_WEIGHT,
        ENERGY_WEIGHT,
        GENRE_WEIGHT,
        MOOD_WEIGHT,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from recommender import (
        ACOUSTIC_WEIGHT,
        ENERGY_WEIGHT,
        GENRE_WEIGHT,
        MOOD_WEIGHT,
    )

# Features the scoring rule actually depends on; a song missing these cannot be
# scored honestly, so it is quarantined rather than silently scored as 0.
REQUIRED_NUMERIC_SONG_FIELDS = ("energy", "acousticness")
REQUIRED_TEXT_SONG_FIELDS = ("genre", "mood")

# Highest score any song can reach (all four signals perfect). Used to normalize
# a raw score into a 0-1 "match strength".
MAX_SCORE = GENRE_WEIGHT + MOOD_WEIGHT + ENERGY_WEIGHT + ACOUSTIC_WEIGHT

# A score gap of this many points over the next-best song is treated as a
# "decisive" ranking margin (margin contribution saturates at 1.0).
MARGIN_SCALE = 1.0

# Confidence below this is treated as "not sure" and flagged for human review
# (used by the self-critique layer).
REVIEW_CONFIDENCE_THRESHOLD = 0.50


class RecommenderInputError(ValueError):
    """Raised when user input is missing or malformed.

    Callers (the CLI, the evaluator) catch this to fail *safely* with a clear
    message instead of crashing with a raw traceback.
    """


def _coerce_pref(user_prefs: Dict[str, Any], *keys: str) -> Any:
    """Return the first present value among ``keys`` (supports both the
    ``favorite_genre`` and shorthand ``genre`` styles used across the codebase)."""
    for key in keys:
        if key in user_prefs and user_prefs[key] not in (None, ""):
            return user_prefs[key]
    return None


def validate_user_prefs(user_prefs: Any) -> None:
    """Validate a user taste profile in place; raise RecommenderInputError if bad.

    A valid profile must name a genre and a mood and give a numeric
    ``target_energy`` in the inclusive range [0, 1] (matching the catalog's
    normalized ``energy`` feature).
    """
    if not isinstance(user_prefs, dict):
        raise RecommenderInputError("User preferences must be provided as a dictionary.")

    genre = _coerce_pref(user_prefs, "favorite_genre", "genre")
    mood = _coerce_pref(user_prefs, "favorite_mood", "mood")
    energy = _coerce_pref(user_prefs, "target_energy", "energy")

    if genre is None or not str(genre).strip():
        raise RecommenderInputError("A non-empty 'favorite_genre' is required.")
    if mood is None or not str(mood).strip():
        raise RecommenderInputError("A non-empty 'favorite_mood' is required.")

    try:
        energy_value = float(energy)
    except (TypeError, ValueError):
        raise RecommenderInputError("'target_energy' must be a number between 0 and 1.")
    if not 0.0 <= energy_value <= 1.0:
        raise RecommenderInputError("'target_energy' must be between 0 and 1.")


def _song_problem(song: Any) -> Optional[str]:
    """Return a human-readable reason a song is unusable, or None if it is fine."""
    if not isinstance(song, dict):
        return "record is not a dictionary"
    for field in REQUIRED_TEXT_SONG_FIELDS:
        if not str(song.get(field, "")).strip():
            return f"missing '{field}'"
    for field in REQUIRED_NUMERIC_SONG_FIELDS:
        try:
            value = float(song.get(field))
        except (TypeError, ValueError):
            return f"invalid '{field}'"
        if not 0.0 <= value <= 1.0:
            return f"'{field}' out of range [0, 1]"
    return None


def validate_songs(songs: Any) -> Tuple[List[Dict], List[Dict]]:
    """Split a catalog into usable and quarantined songs.

    Returns:
        (valid_songs, skipped) where ``skipped`` is a list of
        ``{"song": <record>, "reason": <str>}`` describing why each bad record
        was dropped. This is a guardrail: bad data is isolated and reported,
        not scored as if it were valid.

    Raises:
        RecommenderInputError: if the catalog is empty or nothing survives
        validation (there is no honest recommendation to make in that case).
    """
    if not isinstance(songs, list) or not songs:
        raise RecommenderInputError("The song catalog is empty or not a list.")

    valid: List[Dict] = []
    skipped: List[Dict] = []
    for song in songs:
        problem = _song_problem(song)
        if problem:
            skipped.append({"song": song, "reason": problem})
        else:
            valid.append(song)

    if not valid:
        raise RecommenderInputError("No valid songs remain in the catalog after validation.")

    return valid, skipped


# -----------------------------------------------------------------------------
# Confidence scoring
# -----------------------------------------------------------------------------
# The original recommender returned a raw score but no sense of *how sure* it was.
# Two songs can share a score for very different reasons, and a narrow win over
# the runner-up is far less trustworthy than a decisive one. Confidence turns
# those intuitions into a single, explainable 0-1 number per recommendation.

def compute_match_signals(user_prefs: Dict[str, Any], song: Dict[str, Any]) -> Dict[str, float]:
    """Independently recompute the four match signals from the raw data.

    This is deliberately a *separate* computation from ``recommender.score_song``
    so it can double as a cross-check for the self-critique layer: if the two
    ever disagree, something is wrong.

    Returns a dict with ``genre_match`` and ``mood_match`` (0.0/1.0),
    ``energy_similarity`` and ``acoustic_similarity`` (0.0-1.0), and
    ``completeness`` (fraction of required features present and in range).
    """
    fav_genre = _coerce_pref(user_prefs, "favorite_genre", "genre")
    fav_mood = _coerce_pref(user_prefs, "favorite_mood", "mood")
    target_energy = _coerce_pref(user_prefs, "target_energy", "energy")
    likes_acoustic = bool(user_prefs.get("likes_acoustic", False))
    acoustic_target = 0.8 if likes_acoustic else 0.2

    genre_match = 1.0 if str(song.get("genre", "")).lower() == str(fav_genre).lower() else 0.0
    mood_match = 1.0 if str(song.get("mood", "")).lower() == str(fav_mood).lower() else 0.0

    present = 0
    total = len(REQUIRED_TEXT_SONG_FIELDS) + len(REQUIRED_NUMERIC_SONG_FIELDS)
    for field in REQUIRED_TEXT_SONG_FIELDS:
        if str(song.get(field, "")).strip():
            present += 1

    def _num(field: str) -> Optional[float]:
        try:
            value = float(song.get(field))
        except (TypeError, ValueError):
            return None
        return value if 0.0 <= value <= 1.0 else None

    song_energy = _num("energy")
    song_acoustic = _num("acousticness")
    present += sum(1 for v in (song_energy, song_acoustic) if v is not None)

    energy_similarity = (
        max(0.0, 1.0 - abs(song_energy - float(target_energy))) if song_energy is not None else 0.0
    )
    acoustic_similarity = (
        max(0.0, 1.0 - abs(song_acoustic - acoustic_target)) if song_acoustic is not None else 0.0
    )

    return {
        "genre_match": genre_match,
        "mood_match": mood_match,
        "energy_similarity": round(energy_similarity, 4),
        "acoustic_similarity": round(acoustic_similarity, 4),
        "completeness": round(present / total, 4),
    }


def score_confidence(
    user_prefs: Dict[str, Any],
    song: Dict[str, Any],
    score: float,
    next_best_score: float,
) -> Dict[str, Any]:
    """Rate how confident the system is that ``song`` belongs where it was ranked.

    Confidence blends four transparent factors, each in [0, 1]:

    - ``match_strength``  (0.40): raw score as a fraction of the maximum possible.
    - ``ranking_margin``  (0.30): how decisively it beat the next-best song.
    - ``signal_agreement`` (0.20): fraction of the four signals that are strong.
    - ``completeness``    (0.10): fraction of required features actually present.

    Args:
        score: this song's raw score.
        next_best_score: the score of the next song in the full ranking
            (0.0 if this is the last song), used for the margin factor.

    Returns:
        ``{"confidence": float, "breakdown": {factor: value, ...}}`` with the
        confidence rounded to 3 decimals in [0, 1].
    """
    signals = compute_match_signals(user_prefs, song)

    match_strength = score / MAX_SCORE if MAX_SCORE else 0.0
    margin = max(0.0, score - next_best_score)
    ranking_margin = min(1.0, margin / MARGIN_SCALE) if MARGIN_SCALE else 0.0

    strong_signals = sum(
        1
        for value in (
            signals["genre_match"],
            signals["mood_match"],
            signals["energy_similarity"],
            signals["acoustic_similarity"],
        )
        if value >= 0.5
    )
    signal_agreement = strong_signals / 4.0
    completeness = signals["completeness"]

    confidence = (
        0.40 * match_strength
        + 0.30 * ranking_margin
        + 0.20 * signal_agreement
        + 0.10 * completeness
    )
    confidence = round(max(0.0, min(1.0, confidence)), 3)

    return {
        "confidence": confidence,
        "breakdown": {
            "match_strength": round(match_strength, 4),
            "ranking_margin": round(ranking_margin, 4),
            "signal_agreement": round(signal_agreement, 4),
            "completeness": round(completeness, 4),
        },
    }


def confidence_label(confidence: float) -> str:
    """Map a confidence value to a coarse, human-friendly band."""
    if confidence >= 0.75:
        return "high"
    if confidence >= REVIEW_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


# -----------------------------------------------------------------------------
# Self-critique / validation
# -----------------------------------------------------------------------------
# Before trusting an explanation, the system checks its own work: it re-derives
# the ground truth from the raw data (compute_match_signals) and confirms that
# every claim in the generated explanation is actually supported. Anything that
# cannot be verified - or any low-confidence pick - is flagged for a human to
# review rather than being presented as a confident recommendation. This is the
# guardrail that makes the "act" step of the workflow trustworthy.

def _extract_similarity(explanation: str, label: str) -> Optional[float]:
    """Pull the numeric value out of e.g. 'energy similarity (0.98)'."""
    match = re.search(rf"{label} similarity \(([0-9]*\.?[0-9]+)\)", explanation)
    return float(match.group(1)) if match else None


def critique_recommendation(
    user_prefs: Dict[str, Any],
    song: Dict[str, Any],
    explanation: str,
    confidence: float,
) -> Dict[str, Any]:
    """Verify an explanation's claims against independently recomputed signals.

    Returns:
        {
          "checks": [{"name", "verified", "detail"}, ...],
          "all_verified": bool,        # every claim matched the data
          "needs_review": bool,        # should a human look before trusting it?
          "review_reasons": [str, ...] # why it was flagged (empty if trusted)
        }
    """
    signals = compute_match_signals(user_prefs, song)
    checks: List[Dict[str, Any]] = []

    def add_check(name: str, verified: bool, detail: str) -> None:
        checks.append({"name": name, "verified": bool(verified), "detail": detail})

    # --- categorical claims: does the explanation's match/mismatch wording
    #     agree with the data? ("mismatch" is checked first because it is the
    #     more specific phrase.) ---
    for field, signal_key in (("genre", "genre_match"), ("mood", "mood_match")):
        if f"{field} mismatch" in explanation:
            claimed_match = False
        elif f"{field} match" in explanation:
            claimed_match = True
        else:
            claimed_match = None

        actual_match = signals[signal_key] == 1.0
        if claimed_match is None:
            add_check(f"{field} claim", True, f"no {field} claim to verify")
        else:
            add_check(
                f"{field} claim",
                claimed_match == actual_match,
                f"explanation says {'match' if claimed_match else 'mismatch'}; "
                f"data says {'match' if actual_match else 'mismatch'}",
            )

    # --- numeric claims: does the stated similarity match the recomputed one? ---
    for field, signal_key in (("energy", "energy_similarity"), ("acoustic", "acoustic_similarity")):
        stated = _extract_similarity(explanation, field)
        if stated is None:
            add_check(f"{field} similarity", True, "no numeric claim to verify")
            continue
        expected = round(signals[signal_key], 2)
        add_check(
            f"{field} similarity",
            abs(stated - expected) <= 0.011,  # explanation rounds to 2 decimals
            f"explanation states {stated:.2f}; recomputed {expected:.2f}",
        )

    all_verified = all(check["verified"] for check in checks)

    review_reasons: List[str] = []
    if not all_verified:
        failed = [c["name"] for c in checks if not c["verified"]]
        review_reasons.append(f"unverified claim(s): {', '.join(failed)}")
    if confidence < REVIEW_CONFIDENCE_THRESHOLD:
        review_reasons.append(f"low confidence ({confidence:.2f} < {REVIEW_CONFIDENCE_THRESHOLD:.2f})")
    if signals["completeness"] < 1.0:
        review_reasons.append("incomplete song features")

    return {
        "checks": checks,
        "all_verified": all_verified,
        "needs_review": bool(review_reasons),
        "review_reasons": review_reasons,
    }
