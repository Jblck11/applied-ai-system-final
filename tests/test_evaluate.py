"""Tests for the evaluation harness."""

from src.evaluate import build_report, render_markdown

# A tiny catalog is enough to exercise the harness deterministically.
CATALOG = [
    {"id": 1, "title": "Sunrise City", "artist": "A", "genre": "pop", "mood": "happy",
     "energy": 0.82, "tempo_bpm": 118, "valence": 0.84, "danceability": 0.79, "acousticness": 0.18},
    {"id": 2, "title": "Storm Runner", "artist": "B", "genre": "rock", "mood": "intense",
     "energy": 0.91, "tempo_bpm": 152, "valence": 0.48, "danceability": 0.66, "acousticness": 0.10},
    {"id": 3, "title": "Library Rain", "artist": "C", "genre": "lofi", "mood": "chill",
     "energy": 0.35, "tempo_bpm": 72, "valence": 0.60, "danceability": 0.58, "acousticness": 0.86},
]


def test_build_report_returns_rows_and_metrics():
    rows, metrics = build_report(CATALOG, k=3)
    assert len(rows) == 4  # one row per profile in evaluate.PROFILES
    for key in (
        "consistency_rate",
        "self_critique_pass_rate",
        "average_confidence",
        "review_rate",
        "genre_dominance",
        "total_recommendations",
    ):
        assert key in metrics


def test_system_is_deterministic():
    _, metrics = build_report(CATALOG, k=3)
    assert metrics["consistency_rate"] == 1.0


def test_metrics_are_in_range():
    _, metrics = build_report(CATALOG, k=3)
    for key in ("self_critique_pass_rate", "average_confidence", "review_rate", "genre_dominance"):
        assert 0.0 <= metrics[key] <= 1.0


def test_render_markdown_contains_expected_sections():
    rows, metrics = build_report(CATALOG, k=3)
    report = render_markdown(rows, metrics, k=3)
    assert "# Evaluation Results" in report
    assert "## Reliability Metrics" in report
    assert "## Per-Profile Detail" in report
    # A parseable table row should be present.
    assert "| Profile |" in report
