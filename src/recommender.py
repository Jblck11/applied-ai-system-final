import csv
from dataclasses import dataclass
from typing import Dict, List, Tuple


GENRE_WEIGHT = 2.0
MOOD_WEIGHT = 1.0
ENERGY_WEIGHT = 1.5
ACOUSTIC_WEIGHT = 0.5


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        scored_songs = [
            (self._score_song(user, song), song) for song in self.songs
        ]
        ranked = sorted(scored_songs, key=lambda item: item[0], reverse=True)
        return [song for _, song in ranked[:k]]

    def _score_song(self, user: UserProfile, song: Song) -> float:
        genre_match = 1.0 if song.genre.lower() == user.favorite_genre.lower() else 0.0
        mood_match = 1.0 if song.mood.lower() == user.favorite_mood.lower() else 0.0
        energy_similarity = max(0.0, 1.0 - abs(song.energy - user.target_energy))

        if user.likes_acoustic:
            acoustic_target = 0.8
        else:
            acoustic_target = 0.2
        acoustic_similarity = max(0.0, 1.0 - abs(song.acousticness - acoustic_target))

        score = (
            GENRE_WEIGHT * genre_match
            + MOOD_WEIGHT * mood_match
            + ENERGY_WEIGHT * energy_similarity
            + ACOUSTIC_WEIGHT * acoustic_similarity
        )
        return round(score, 4)

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        score = self._score_song(user, song)
        reasons: List[str] = []

        if song.genre.lower() == user.favorite_genre.lower():
            reasons.append("genre matched your favorite genre")
        else:
            reasons.append("genre did not match your favorite genre")

        if song.mood.lower() == user.favorite_mood.lower():
            reasons.append("mood matched your favorite mood")
        else:
            reasons.append("mood did not match your favorite mood")

        energy_distance = abs(song.energy - user.target_energy)
        reasons.append(
            f"energy was {energy_distance:.2f} away from your target, giving an energy similarity score"
        )

        return f"Score {score:.2f} because: {'; '.join(reasons)}."


def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file into a list of dictionaries."""
    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            numeric_fields = [
                "energy",
                "tempo_bpm",
                "valence",
                "danceability",
                "acousticness",
            ]
            converted_row = dict(row)
            for field in numeric_fields:
                converted_row[field] = float(row[field])
            converted_row["id"] = int(row["id"])
            songs.append(converted_row)
    return songs


def _get_preferred_acousticness(user_prefs: Dict) -> float:
    """Return the acoustic target implied by the user's preference."""
    likes_acoustic = user_prefs.get("likes_acoustic", False)
    return 0.8 if likes_acoustic else 0.2


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score a single song against a user's preferences and explain why."""
    preferred_genre = user_prefs.get("favorite_genre", user_prefs.get("genre", ""))
    preferred_mood = user_prefs.get("favorite_mood", user_prefs.get("mood", ""))
    target_energy = user_prefs.get("target_energy", user_prefs.get("energy", 0.0))
    preferred_acousticness = _get_preferred_acousticness(user_prefs)

    genre_match = 1.0 if str(song.get("genre", "")).lower() == str(preferred_genre).lower() else 0.0
    mood_match = 1.0 if str(song.get("mood", "")).lower() == str(preferred_mood).lower() else 0.0
    energy_similarity = max(0.0, 1.0 - abs(float(song.get("energy", 0.0)) - float(target_energy)))
    acoustic_similarity = max(0.0, 1.0 - abs(float(song.get("acousticness", 0.0)) - preferred_acousticness))

    score = (
        GENRE_WEIGHT * genre_match
        + MOOD_WEIGHT * mood_match
        + ENERGY_WEIGHT * energy_similarity
        + ACOUSTIC_WEIGHT * acoustic_similarity
    )

    reasons: List[str] = []
    if genre_match:
        reasons.append("genre match (+2.0)")
    else:
        reasons.append("genre mismatch")
    if mood_match:
        reasons.append("mood match (+1.0)")
    else:
        reasons.append("mood mismatch")
    reasons.append(f"energy similarity ({energy_similarity:.2f})")
    reasons.append(f"acoustic similarity ({acoustic_similarity:.2f})")

    return round(score, 2), reasons


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Rank songs by a scoring rule and return the top-k recommendations."""
    scored_songs: List[Tuple[float, Dict, str]] = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        explanation = f"Score {score:.2f} because: {', '.join(reasons)}"
        scored_songs.append((score, song, explanation))

    ranked = sorted(scored_songs, key=lambda item: item[0], reverse=True)
    return [(song, score, explanation) for score, song, explanation in ranked[:k]]
