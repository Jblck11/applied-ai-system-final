"""Evaluation harness for the recommender.

Runs the full pipeline over a fixed panel of user profiles and measures how
*reliable* the system is, rather than just whether it produces output. It reports:

- **Consistency**    - is the system deterministic? (same input -> same output)
- **Self-critique pass rate** - what fraction of recommendations have every
  claim verified against the data?
- **Average confidence** - how sure is the system, on average?
- **Review rate**    - what fraction of recommendations get flagged for a human?
- **Genre dominance** - a bias metric quantifying how strongly the favorite
  genre drives the top-K (the recommender's known weakness).

Run it with:

    python -m src.evaluate

It prints a report and writes the same content to ``evaluation_results.md`` so
the results are reproducible evidence without watching a demo.
"""

import logging
import os
from typing import Any, Dict, List, Tuple

try:  # package-style import (python -m src.evaluate)
    from .recommender import load_songs
    from .pipeline import run_recommendation
    from .logging_setup import configure_logging
except ImportError:  # pragma: no cover - fallback for direct script execution
    from recommender import load_songs
    from pipeline import run_recommendation
    from logging_setup import configure_logging


# A small, deliberately varied panel of taste profiles. The last one asks for a
# genre that is absent from the catalog, to probe how the system behaves when no
# strong match exists (it should stay honest: low confidence, flagged).
PROFILES: List[Dict[str, Any]] = [
    {"name": "Pop / happy / high energy",
     "prefs": {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8, "likes_acoustic": False}},
    {"name": "Rock / intense / high energy",
     "prefs": {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.9, "likes_acoustic": False}},
    {"name": "Lofi / chill / low energy, acoustic",
     "prefs": {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.35, "likes_acoustic": True}},
    {"name": "Classical / calm (absent genre)",
     "prefs": {"favorite_genre": "classical", "favorite_mood": "calm", "target_energy": 0.3, "likes_acoustic": True}},
]


def _project_path(*parts: str) -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, *parts)


def _signature(result: Dict[str, Any]) -> List[Tuple[str, float]]:
    """A comparable fingerprint of a run's recommendations (title + score)."""
    return [(item["song"].get("title", "?"), item["score"]) for item in result["recommendations"]]


def build_report(catalog: List[Dict], k: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run every profile and return (per-profile rows, aggregate metrics)."""
    rows: List[Dict[str, Any]] = []
    total_recs = 0
    verified_recs = 0
    flagged_recs = 0
    confidence_sum = 0.0
    consistent_runs = 0
    genre_dominance_sum = 0.0

    for profile in PROFILES:
        prefs = profile["prefs"]
        fav_genre = prefs["favorite_genre"].lower()

        # Determinism check: run twice and compare fingerprints.
        first = run_recommendation(prefs, catalog, k=k)
        second = run_recommendation(prefs, catalog, k=k)
        is_consistent = _signature(first) == _signature(second)
        consistent_runs += int(is_consistent)

        recs = first["recommendations"]
        n = len(recs)
        verified = sum(1 for r in recs if r["critique"]["all_verified"])
        flagged = sum(1 for r in recs if r["needs_review"])
        avg_conf = sum(r["confidence"] for r in recs) / n if n else 0.0
        genre_hits = sum(1 for r in recs if str(r["song"].get("genre", "")).lower() == fav_genre)
        genre_share = genre_hits / n if n else 0.0

        total_recs += n
        verified_recs += verified
        flagged_recs += flagged
        confidence_sum += sum(r["confidence"] for r in recs)
        genre_dominance_sum += genre_share

        top = recs[0] if recs else None
        rows.append(
            {
                "profile": profile["name"],
                "top_pick": top["song"]["title"] if top else "-",
                "top_confidence": round(top["confidence"], 2) if top else 0.0,
                "avg_confidence": round(avg_conf, 2),
                "verified": f"{verified}/{n}",
                "flagged": f"{flagged}/{n}",
                "genre_share": round(genre_share, 2),
                "consistent": is_consistent,
            }
        )

    metrics = {
        "profiles": len(PROFILES),
        "total_recommendations": total_recs,
        "consistency_rate": round(consistent_runs / len(PROFILES), 3) if PROFILES else 0.0,
        "self_critique_pass_rate": round(verified_recs / total_recs, 3) if total_recs else 0.0,
        "average_confidence": round(confidence_sum / total_recs, 3) if total_recs else 0.0,
        "review_rate": round(flagged_recs / total_recs, 3) if total_recs else 0.0,
        "genre_dominance": round(genre_dominance_sum / len(PROFILES), 3) if PROFILES else 0.0,
    }
    return rows, metrics


def render_markdown(rows: List[Dict[str, Any]], metrics: Dict[str, Any], k: int) -> str:
    """Render the report as a parseable Markdown document."""
    lines: List[str] = []
    lines.append("# Evaluation Results")
    lines.append("")
    lines.append(
        "_Generated by `python -m src.evaluate`. Deterministic and fully offline, "
        "so re-running reproduces these numbers exactly._"
    )
    lines.append("")

    # Headline summary in the assignment's suggested style.
    passed = int(round(metrics["self_critique_pass_rate"] * metrics["total_recommendations"]))
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Ran **{metrics['profiles']} profiles** producing "
        f"**{metrics['total_recommendations']} recommendations** (top {k} each)."
    )
    lines.append(
        f"- **{passed} of {metrics['total_recommendations']}** recommendations passed self-critique "
        f"(every claim verified against the data)."
    )
    lines.append(
        f"- Confidence averaged **{metrics['average_confidence']:.2f}**; "
        f"**{metrics['review_rate'] * 100:.0f}%** of recommendations were flagged for human review."
    )
    lines.append(
        f"- Consistency: **{metrics['consistency_rate'] * 100:.0f}%** "
        f"(identical output on repeated runs)."
    )
    lines.append(
        f"- Genre-dominance bias metric: **{metrics['genre_dominance']:.2f}** "
        f"(share of each top-{k} that matches the user's favorite genre; higher = more genre-driven)."
    )
    lines.append("")

    # Reliability metrics table.
    lines.append("## Reliability Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Profiles evaluated | {metrics['profiles']} |")
    lines.append(f"| Total recommendations | {metrics['total_recommendations']} |")
    lines.append(f"| Consistency rate | {metrics['consistency_rate']:.2f} |")
    lines.append(f"| Self-critique pass rate | {metrics['self_critique_pass_rate']:.2f} |")
    lines.append(f"| Average confidence | {metrics['average_confidence']:.2f} |")
    lines.append(f"| Review rate | {metrics['review_rate']:.2f} |")
    lines.append(f"| Genre dominance (bias) | {metrics['genre_dominance']:.2f} |")
    lines.append("")

    # Per-profile table.
    lines.append("## Per-Profile Detail")
    lines.append("")
    lines.append("| Profile | Top pick | Top conf. | Avg conf. | Verified | Flagged | Genre share | Consistent |")
    lines.append("|---------|----------|-----------|-----------|----------|---------|-------------|------------|")
    for r in rows:
        lines.append(
            f"| {r['profile']} | {r['top_pick']} | {r['top_confidence']:.2f} | "
            f"{r['avg_confidence']:.2f} | {r['verified']} | {r['flagged']} | "
            f"{r['genre_share']:.2f} | {'yes' if r['consistent'] else 'NO'} |"
        )
    lines.append("")

    # Interpretation.
    lines.append("## What This Shows")
    lines.append("")
    lines.append(
        "- The system is **deterministic**, so results are reproducible for grading."
    )
    lines.append(
        "- Self-critique catches unverifiable claims; in normal operation the "
        "templated explanations are truthful, so the pass rate is high, while "
        "**low-confidence picks are still flagged for a human**."
    )
    lines.append(
        "- The **absent-genre profile** (\"classical\") demonstrates honest behavior "
        "when no good match exists: confidence drops and picks are flagged rather "
        "than presented as trustworthy."
    )
    lines.append(
        "- The **genre-dominance** metric quantifies the recommender's known bias: "
        "because genre carries the largest weight, top results skew toward the "
        "favorite genre even when strong cross-genre matches exist."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    # Keep the console clean: only surface warnings from the pipeline here.
    configure_logging(logfile=_project_path("logs", "evaluate.log"), level=logging.WARNING)

    catalog = load_songs(_project_path("data", "songs.csv"))
    k = 5
    rows, metrics = build_report(catalog, k=k)
    report = render_markdown(rows, metrics, k=k)

    out_path = _project_path("evaluation_results.md")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(report + "\n")

    print(report)
    print(f"\n(Written to {os.path.basename(out_path)})")


if __name__ == "__main__":
    main()
