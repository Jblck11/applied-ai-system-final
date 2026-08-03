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

from typing import Any, Dict, List, Optional, Tuple

# Features the scoring rule actually depends on; a song missing these cannot be
# scored honestly, so it is quarantined rather than silently scored as 0.
REQUIRED_NUMERIC_SONG_FIELDS = ("energy", "acousticness")
REQUIRED_TEXT_SONG_FIELDS = ("genre", "mood")


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
