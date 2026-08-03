# System Architecture

The **canonical source** for the architecture diagram is [`architecture.mmd`](architecture.mmd)
(Mermaid source). Edit that file, then optionally export a PNG into
[`../assets/`](../assets/) for embedding in the main README.

To preview or export: open <https://mermaid.live> and paste the contents of
`architecture.mmd`.

- **Solid nodes** = the current Module-3 Music Recommender (input → load catalog →
  score → rank → explain → output), plus the pytest suite that checks the results.
- **Dashed nodes** = the planned final-project AI extension (retrieval, grounded
  explanation, self-critique/validation, confidence scoring, human/test review).
  These are **not yet implemented** — they mark where new components will slot in.

The diagram below is a rendered copy kept in sync with `architecture.mmd` so it
displays directly on GitHub.

```mermaid
flowchart TD
    U([User taste profile<br/>genre &bull; mood &bull; target energy &bull; likes acoustic]):::user
    CSV[("data/songs.csv<br/>song catalog")]:::data

    subgraph CORE["Recommender Core &mdash; src/recommender.py"]
        direction TB
        L["load_songs()<br/>parse catalog"] --> S["_score_song()<br/>weighted match:<br/>genre + mood + energy + acoustic"]
        S --> RK["recommend()<br/>rank &rarr; top-K"]
        RK --> EX["explain_recommendation()<br/>plain-English reasons"]
    end

    subgraph UI["Interface &mdash; src/main.py (CLI)"]
        OUT[/"Ranked recommendations<br/>+ score + explanation"/]:::out
    end

    subgraph TESTS["Verification &mdash; tests/test_recommender.py"]
        T["pytest unit tests<br/>scoring &bull; ranking &bull; edge cases"]:::test
    end

    U --> L
    CSV --> L
    EX --> OUT
    OUT --> U

    T -. "asserts against" .-> S
    T -. "asserts against" .-> RK

    RK -. planned .-> RET["Retriever (RAG)<br/>fetch song/artist facts"]:::planned
    RET -. planned .-> GEN["LLM explanation<br/>grounded in retrieved facts"]:::planned
    GEN -. planned .-> CRIT["Self-critique + validation<br/>check claims vs. data"]:::planned
    CRIT -. planned .-> CONF["Confidence score<br/>0.0&ndash;1.0 per recommendation"]:::planned
    CONF -. "feeds richer output" .-> OUT
    CRIT -. "low confidence -> flag" .-> HUMAN{{"Human / test review<br/>of flagged results"}}:::planned

    classDef user fill:#e8f0fe,stroke:#4285f4,color:#111;
    classDef data fill:#e6f4ea,stroke:#34a853,color:#111;
    classDef out fill:#f3e8fd,stroke:#a142f4,color:#111;
    classDef test fill:#fef7e0,stroke:#f9ab00,color:#111;
    classDef planned fill:#f1f3f4,stroke:#9aa0a6,color:#5f6368,stroke-dasharray:5 5;
```

## Legend

| Layer | Component | Role |
|-------|-----------|------|
| Input | User taste profile + `data/songs.csv` | Preferences and the song catalog |
| Core | `src/recommender.py` | Scores, ranks, and explains recommendations |
| Interface | `src/main.py` (CLI) | Runs the pipeline and prints results |
| Verification | `tests/test_recommender.py` | pytest checks on scoring, ranking, edge cases |
| *Planned* | Retriever · LLM explainer · Self-critique · Confidence | The final-project AI feature (not yet built) |
