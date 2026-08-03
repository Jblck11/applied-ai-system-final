"""Tests for the reliability layer (input validation / guardrails).

Confidence-scoring and self-critique tests are added alongside those features
in later commits.
"""

import pytest

from src.reliability import (
    RecommenderInputError,
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
