# 🎧 Model Card: VibeFinder (Trustworthy Music Recommender)

> Base project: **AI110 Module 3 — Music Recommender Simulation**, extended with a
> reliability layer (confidence scoring + self-critique + guardrails + evaluation).

---

## 1. Model Name

**VibeFinder 1.0** — a transparent, offline music recommender with built-in
confidence scoring and self-critique.

---

## 2. Intended Use

- **What it generates:** a ranked top-K list of songs for a user's taste
  profile, each with a plain-English explanation *and* a confidence score, plus
  a flag when the system isn't sure enough to be trusted without a human look.
- **Assumptions about the user:** the user can express a single favorite genre,
  a single favorite mood, a target energy level (0–1), and whether they prefer
  acoustic music. It assumes taste can be approximated by these few features.
- **Audience / context:** this is a **classroom exploration** of recommender
  systems and responsible AI, not a production system for real listeners. It is
  designed to make the *reasoning and reliability* of a recommender visible.

---

## 3. How the Model Works

Imagine giving a friend four notes about yourself: a genre you love, a mood you
want, how energetic you feel, and whether you like acoustic music. The system
looks at every song and gives it points for matching each of those, adding up to
a score. Songs with the most points rise to the top.

The new part is that the system also asks itself two honest questions about each
pick: **"How sure am I?"** and **"Is what I just said actually true?"**

- For *how sure*, it combines how strongly the song matched, how clearly it beat
  the next song, how many of the four signals agreed, and whether the song's data
  was complete — into a single confidence number from 0 to 1.
- For *is it true*, it re-checks the data from scratch and confirms every claim
  in its explanation (e.g. if it said "genre match," it verifies that).

If it isn't confident, or a claim can't be verified, it **flags the pick for a
human** instead of pretending to be sure.

**Changes from the starter logic:** the original just scored, ranked, and
explained. I added input validation, a confidence score, a self-critique step, a
human-review flag, logging, and an evaluation harness that measures reliability.

---

## 4. Data

- **Catalog size:** 18 songs (`data/songs.csv`).
- **Features per song:** genre, mood, energy, tempo, valence, danceability,
  acousticness.
- **Genres/moods represented:** a handful — pop, lofi, rock, and a few others;
  moods like happy, chill, intense.
- **Changes to data:** none — I kept the original catalog so results stay
  comparable to Module 3.
- **What's missing:** the catalog is tiny and skews toward a few genres. Whole
  categories of taste (e.g. classical, jazz, world, hip-hop nuance) are absent or
  thin, and there is no information about lyrics, language, artist popularity, or
  listening history.

---

## 5. Strengths

- **Works well for clear, single-genre tastes** (e.g. "lofi / chill / acoustic"):
  it returns strong same-genre matches with high confidence and nothing flagged.
- **It is honest about close calls.** When the #1 and #2 songs are nearly tied,
  confidence drops to "medium" even though the score is high — the ranking-margin
  factor captures that the ordering isn't clear-cut.
- **It fails safely.** Missing/invalid input and malformed catalog rows are
  caught and reported instead of crashing.
- **It is reproducible.** Fully offline and deterministic, so the same input
  always gives the same output — which is what makes its reliability claims
  meaningful.

---

## 6. Limitations and Bias

- **Genre dominance (measured):** genre carries the largest weight, so top
  results skew toward the favorite genre even when a strong cross-genre match
  exists. The evaluation reports a **genre-dominance metric of 0.35**; a great
  mood match in a different genre can be buried under a mediocre same-genre song.
- **Features it ignores:** lyrics, language, tempo/valence/danceability (present
  in the data but unused by the score), artist, and any notion of novelty or
  diversity.
- **Tiny, skewed catalog:** with 18 songs and thin genre coverage, users whose
  taste isn't represented (e.g. the "classical" test profile) get only weak
  matches — the system correctly reports low confidence and flags them, but it
  still can't serve those users well.
- **Confidence is a heuristic, not a probability.** It is a transparent, tunable
  blend of four factors, not a calibrated likelihood; the 0.50 review threshold
  is a reasonable default, not a learned boundary.
- **Self-critique verifies internal consistency, not real-world "good taste."**
  It confirms the explanation matches the data; it cannot know whether the
  recommendation is one the listener will actually enjoy.

---

## 7. Evaluation / Testing Results

Measured with `python -m src.evaluate` over 4 profiles / 20 recommendations, and
`python -m pytest` (see [`evaluation_results.md`](evaluation_results.md)):

| Metric | Result |
|--------|--------|
| Automated tests passing | **34 / 34** |
| Consistency (determinism) | **100%** |
| Self-critique pass rate | **100%** (every claim verified) |
| Average confidence | **0.61** |
| Recommendations flagged for review | **50%** |
| Genre-dominance (bias) | **0.35** |

**Profiles tested:** pop/happy, rock/intense, lofi/chill (acoustic), and a
deliberate edge case — "classical," a genre absent from the catalog.

**What I looked for and what surprised me:** I checked that strong matches were
confident and weak ones were flagged. The surprise was the "classical" profile:
the system still returned five songs, but dropped confidence and flagged 4 of 5 —
exactly the honest behavior I wanted, without any special-casing. It also
surprised me that the highest-scoring song sometimes gets only *medium*
confidence when it barely beats the runner-up.

---

## 8. Future Work

- Add a **diversity / re-ranking** step so the top-K isn't dominated by one
  genre (directly addressing the measured bias).
- Use more of the existing features (valence, danceability, tempo) in scoring.
- **Calibrate** the confidence score against human judgments instead of using
  fixed weights.
- Generate richer natural-language explanations (e.g. via an LLM) while keeping
  the self-critique as a grounding guardrail — the architecture already leaves a
  slot for this.
- Grow and rebalance the catalog so more tastes are representable.

---

## 9. Responsible-AI Reflection

### How I collaborated with AI

I built this project in partnership with an AI coding assistant (Claude Code). I
set the direction and made the decisions; the assistant proposed designs, wrote
code against my choices, and ran the tests. We worked in small, reviewable
commits — validation, then confidence, then self-critique, then evaluation, then
docs — and I checked the output of each step (tests passing, sample runs) before
moving on.

### One helpful AI suggestion

The assistant proposed framing the whole extension as a **reliability layer**
(confidence + self-critique + review flags) rather than swapping in a fancier
model. That reframing was the backbone of the project: it turned "make the
recommender better" into "make the recommender *honest*," which is a much
stronger responsible-AI story and fit the offline, reproducible constraint. It
also suggested having the self-critique **recompute the match signals
independently** so it acts as a real cross-check — a subtle idea I would not have
had on my own.

### One flawed AI suggestion

Early on, when I asked for the *easiest* project to extend, the assistant
recommended **BugHound (Module 5)** because it already had an agentic loop and
guardrails. That was wrong for my situation: the assignment requires the base
project to come from **Modules 1–3**, and BugHound is a Module 5 "tinker" starter
(mostly instructor-provided code). We caught this only when I shared the full
requirements, and switched the base to my own Module 3 project. Lesson: an AI's
"easiest" answer optimizes for the goal you state, not the constraints you forgot
to mention — I had to bring the actual rubric before its advice was trustworthy.

### Biases in the system

The system has a built-in **genre bias** (measured at 0.35): because genre is the
heaviest-weighted signal, recommendations skew toward the user's favorite genre
and can bury strong cross-genre matches. The tiny, genre-skewed catalog
compounds this, so users whose taste isn't represented are served poorly. I chose
to **measure and disclose** this bias (via the evaluation metric and this card)
rather than hide it.

### The system's limitations

VibeFinder only understands four coarse features of taste, runs on an 18-song
catalog, and produces templated (not free-form) explanations. Its confidence is a
transparent heuristic, not a calibrated probability, and its self-critique
verifies internal consistency, not whether a listener will actually like a song.
It is a classroom demonstration of *trustworthy design*, not a production
recommender.

---

## 10. Personal Reflection

The biggest thing I learned is that a trustworthy AI system isn't necessarily a
more complex one — it's one that knows and communicates its own limits. Adding
confidence and self-critique changed how I read the output: instead of trusting a
ranked list because it looked authoritative, I could see *which* picks the system
had actually earned. The most interesting discovery was that measuring
reliability made the model's flaws (like genre bias and shaky close calls)
visible and honest, rather than hidden. It changed how I think about the music
apps I use every day — every confident-looking recommendation is a scored guess,
and the responsible thing is to show the uncertainty, not paper over it.
