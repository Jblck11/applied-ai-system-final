"""Tests for the reliability layer (input validation / guardrails).

Confidence-scoring and self-critique tests are added alongside those features
in later commits.
"""

import pytest

from src.reliability import (
    MAX_SCORE,
    RecommenderInputError,
    compute_match_signals,
    confidence_label,
    critique_recommendation,
    score_confidence,
    validate_songs,
    validate_user_prefs,
)


def _good_song(**overrides):
    song = {
        "id": 1,
        "title": "Test Track",
        "artist": "Tester",
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "acousticness": 0.2,
    }
    song.update(overrides)
    return song


# ---- user profile validation ------------------------------------------------

def test_valid_profile_passes():
    validate_user_prefs(
        {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    )  # should not raise


def test_shorthand_keys_are_accepted():
    validate_user_prefs({"genre": "pop", "mood": "happy", "energy": 0.5})


@pytest.mark.parametrize(
    "prefs",
    [
        {},                                                        # empty
        {"favorite_mood": "happy", "target_energy": 0.5},          # no genre
        {"favorite_genre": "pop", "target_energy": 0.5},           # no mood
        {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": "loud"},  # bad energy
        {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 5},        # out of range
    ],
)
def test_bad_profiles_are_rejected(prefs):
    with pytest.raises(RecommenderInputError):
        validate_user_prefs(prefs)


def test_non_dict_profile_rejected():
    with pytest.raises(RecommenderInputError):
        validate_user_prefs("pop, happy, loud")


# ---- catalog validation -----------------------------------------------------

def test_valid_catalog_returns_all_songs_and_no_skips():
    valid, skipped = validate_songs([_good_song(id=1), _good_song(id=2)])
    assert len(valid) == 2
    assert skipped == []


def test_bad_songs_are_quarantined_with_reasons():
    catalog = [
        _good_song(id=1),
        _good_song(id=2, genre=""),           # missing genre
        _good_song(id=3, energy="fast"),      # invalid energy
        _good_song(id=4, acousticness=9.0),   # out of range
    ]
    valid, skipped = validate_songs(catalog)
    assert len(valid) == 1
    assert {s["reason"] for s in skipped} == {
        "missing 'genre'",
        "invalid 'energy'",
        "'acousticness' out of range [0, 1]",
    }


def test_empty_catalog_raises():
    with pytest.raises(RecommenderInputError):
        validate_songs([])


def test_all_invalid_catalog_raises():
    with pytest.raises(RecommenderInputError):
        validate_songs([_good_song(genre=""), _good_song(mood="")])


# ---- match signals ----------------------------------------------------------

def test_match_signals_perfect_match():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    signals = compute_match_signals(prefs, _good_song(energy=0.8, acousticness=0.2))
    assert signals["genre_match"] == 1.0
    assert signals["mood_match"] == 1.0
    assert signals["energy_similarity"] == pytest.approx(1.0)
    assert signals["acoustic_similarity"] == pytest.approx(1.0)
    assert signals["completeness"] == 1.0


def test_match_signals_mismatch():
    prefs = {"favorite_genre": "rock", "favorite_mood": "sad", "target_energy": 0.1}
    signals = compute_match_signals(prefs, _good_song(genre="pop", mood="happy", energy=0.9))
    assert signals["genre_match"] == 0.0
    assert signals["mood_match"] == 0.0
    assert signals["energy_similarity"] < 0.5


# ---- confidence scoring -----------------------------------------------------

def test_confidence_is_bounded():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    out = score_confidence(prefs, _good_song(), score=MAX_SCORE, next_best_score=0.0)
    assert 0.0 <= out["confidence"] <= 1.0
    assert set(out["breakdown"]) == {
        "match_strength",
        "ranking_margin",
        "signal_agreement",
        "completeness",
    }


def test_strong_decisive_match_beats_weak_narrow_match():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}

    strong = score_confidence(
        prefs, _good_song(energy=0.8, acousticness=0.2), score=4.9, next_best_score=2.0
    )
    weak = score_confidence(
        prefs,
        _good_song(genre="jazz", mood="sad", energy=0.1),
        score=1.9,
        next_best_score=1.85,
    )
    assert strong["confidence"] > weak["confidence"]


def test_ranking_margin_raises_confidence():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    song = _good_song()
    decisive = score_confidence(prefs, song, score=4.0, next_best_score=1.0)
    narrow = score_confidence(prefs, song, score=4.0, next_best_score=3.95)
    assert decisive["confidence"] > narrow["confidence"]


@pytest.mark.parametrize(
    "value,expected",
    [(0.9, "high"), (0.75, "high"), (0.6, "medium"), (0.5, "medium"), (0.3, "low"), (0.0, "low")],
)
def test_confidence_label_bands(value, expected):
    assert confidence_label(value) == expected


# ---- self-critique / validation ---------------------------------------------

PREFS = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}


def test_truthful_explanation_is_verified_and_trusted():
    song = _good_song(genre="pop", mood="happy", energy=0.8, acousticness=0.2)
    explanation = (
        "Score 4.96 because: genre match (+2.0), mood match (+1.0), "
        "energy similarity (1.00), acoustic similarity (1.00)"
    )
    result = critique_recommendation(PREFS, song, explanation, confidence=0.95)
    assert result["all_verified"] is True
    assert result["needs_review"] is False
    assert result["review_reasons"] == []


def test_false_categorical_claim_is_caught():
    # Data says genre does NOT match, but the explanation claims it does.
    song = _good_song(genre="rock", mood="happy", energy=0.8, acousticness=0.2)
    explanation = (
        "Score 4.96 because: genre match (+2.0), mood match (+1.0), "
        "energy similarity (1.00), acoustic similarity (1.00)"
    )
    result = critique_recommendation(PREFS, song, explanation, confidence=0.95)
    assert result["all_verified"] is False
    assert result["needs_review"] is True
    assert any("genre" in c["name"] and not c["verified"] for c in result["checks"])


def test_false_numeric_claim_is_caught():
    # Energy similarity should be ~1.00, but the explanation understates it badly.
    song = _good_song(genre="pop", mood="happy", energy=0.8, acousticness=0.2)
    explanation = (
        "Score 4.96 because: genre match (+2.0), mood match (+1.0), "
        "energy similarity (0.10), acoustic similarity (1.00)"
    )
    result = critique_recommendation(PREFS, song, explanation, confidence=0.95)
    assert result["all_verified"] is False
    assert any("energy" in c["name"] and not c["verified"] for c in result["checks"])


def test_low_confidence_forces_review_even_when_verified():
    song = _good_song(genre="pop", mood="happy", energy=0.8, acousticness=0.2)
    explanation = (
        "Score 4.96 because: genre match (+2.0), mood match (+1.0), "
        "energy similarity (1.00), acoustic similarity (1.00)"
    )
    result = critique_recommendation(PREFS, song, explanation, confidence=0.10)
    assert result["all_verified"] is True
    assert result["needs_review"] is True
    assert any("low confidence" in r for r in result["review_reasons"])
