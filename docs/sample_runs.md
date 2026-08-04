# Sample Runs (reproducible evidence)

These are **real, unedited** console captures. Re-running the same commands from
the repository root reproduces them exactly (the system is deterministic and
fully offline). This is the interaction-log evidence for the project — no video
required.

---

## Sample 1 — default profile (pop / happy / high energy)

Command:

```bash
python -m src.main
```

Output:

```text
20:03:32 | INFO    | LOAD: 18 songs from data\songs.csv
20:03:32 | INFO    | PLAN: validate -> score -> rank -> return top 5
20:03:32 | INFO    | VALIDATE-INPUT: user profile accepted.
20:03:32 | INFO    | VALIDATE-CATALOG: 18 song(s) usable.
20:03:32 | INFO    | RANK: scored 18 song(s); returning top 5.
20:03:32 | INFO    | CONFIDENCE: average 0.657 across 5 recommendation(s).
20:03:32 | INFO    | SELF-CRITIQUE: 2 of 5 recommendation(s) flagged for human review.

Loaded songs: 18 usable

Top recommendations:

Sunrise City             | Score:  4.96 | Confidence: 1.00 (high  )         | Score 4.96 because: genre match (+2.0), mood match (+1.0), energy similarity (0.98), acoustic similarity (0.98)
Gym Hero                 | Score:  3.73 | Confidence: 0.81 (high  )         | Score 3.73 because: genre match (+2.0), mood mismatch, energy similarity (0.87), acoustic similarity (0.85)
Rooftop Lights           | Score:  2.87 | Confidence: 0.77 (high  )         | Score 2.87 because: genre mismatch, mood match (+1.0), energy similarity (0.96), acoustic similarity (0.85)
Night Drive Loop         | Score:  1.91 | Confidence: 0.36 (low   )  REVIEW | Score 1.91 because: genre mismatch, mood mismatch, energy similarity (0.95), acoustic similarity (0.98)
                           -> flagged for review: low confidence (0.36 < 0.50)
Winter Window            | Score:  1.88 | Confidence: 0.35 (low   )  REVIEW | Score 1.88 because: genre mismatch, mood mismatch, energy similarity (0.94), acoustic similarity (0.95)
                           -> flagged for review: low confidence (0.35 < 0.50)

Self-critique: 3/5 recommendation(s) verified and trusted; 2 flagged for human review.
```

**Reading it:** the two strong same-genre matches are trusted with high
confidence; the two songs that match neither genre nor mood are correctly
flagged for a human because confidence fell below 0.50.

---

## Sample 2 — a different profile (lofi / chill / acoustic), top 3

Command:

```bash
python -m src.main --genre lofi --mood chill --energy 0.35 --acoustic -k 3
```

Output:

```text
20:03:33 | INFO    | CONFIDENCE: average 0.855 across 3 recommendation(s).
20:03:33 | INFO    | SELF-CRITIQUE: 0 of 3 recommendation(s) flagged for human review.

Loaded songs: 18 usable

Top recommendations:

Library Rain             | Score:  4.97 | Confidence: 0.73 (medium)         | Score 4.97 because: genre match (+2.0), mood match (+1.0), energy similarity (1.00), acoustic similarity (0.94)
Midnight Coding          | Score:  4.85 | Confidence: 0.97 (high  )         | Score 4.85 because: genre match (+2.0), mood match (+1.0), energy similarity (0.93), acoustic similarity (0.91)
Focus Flow               | Score:  3.92 | Confidence: 0.86 (high  )         | Score 3.92 because: genre match (+2.0), mood mismatch, energy similarity (0.95), acoustic similarity (0.98)

Self-critique: 3/3 recommendation(s) verified and trusted; 0 flagged for human review.
```

**Reading it:** note that *Library Rain* has the **highest score** but only
**medium confidence** — it barely edged out *Midnight Coding*, so the system is
honest that the #1 ordering is not clear-cut. This is the ranking-margin factor
of the confidence score in action.

---

## Sample 3 — invalid input is handled safely (guardrail)

Command:

```bash
python -m src.main --genre ""
```

Output:

```text
20:03:33 | INFO    | LOAD: 18 songs from data\songs.csv
20:03:33 | INFO    | PLAN: validate -> score -> rank -> return top 5
20:03:33 | ERROR   | Input rejected: A non-empty 'favorite_genre' is required.

Could not produce recommendations: A non-empty 'favorite_genre' is required.
```

**Reading it:** bad input is rejected with a clear message and a logged ERROR,
instead of crashing with a traceback.

---

## Evaluation harness

Command:

```bash
python -m src.evaluate
```

This prints and writes [`../evaluation_results.md`](../evaluation_results.md),
the reliability metrics report (consistency, self-critique pass rate, average
confidence, review rate, and the genre-dominance bias metric).
