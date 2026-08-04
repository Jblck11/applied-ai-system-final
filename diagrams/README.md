# System Architecture

The **canonical source** for the architecture diagram is [`architecture.mmd`](architecture.mmd)
(Mermaid source). Edit that file, then optionally export a PNG into
[`../assets/`](../assets/) for embedding in the main README.

To preview or export: open <https://mermaid.live> and paste the contents of
`architecture.mmd`.

Data flows **input → guardrails → score & rank → confidence → self-critique →
decision → output**, with a human-review checkpoint for anything the system
cannot verify or isn't confident about. The pytest suite and the evaluation
harness check the AI results at the points shown.

The diagram below is a rendered copy kept in sync with `architecture.mmd` so it
displays directly on GitHub.

```mermaid
flowchart TD
    U([User taste profile<br/>genre &bull; mood &bull; target energy &bull; likes acoustic]):::user
    CSV[("data/songs.csv<br/>song catalog")]:::data

    subgraph GUARD["Guardrails &mdash; reliability.py"]
        VP["validate_user_prefs()<br/>reject bad profiles"]:::guard
        VS["validate_songs()<br/>quarantine bad rows"]:::guard
    end

    subgraph CORE["Recommender Core &mdash; recommender.py"]
        direction TB
        SC1["score_song()<br/>weighted match:<br/>genre + mood + energy + acoustic"] --> RK["recommend_songs()<br/>rank &rarr; top-K + explanation"]
    end

    subgraph REL["Reliability Layer &mdash; reliability.py"]
        direction TB
        CONF["score_confidence()<br/>match strength &bull; ranking margin<br/>signal agreement &bull; completeness &rarr; 0-1"]:::rel
        CRIT["critique_recommendation()<br/>re-derive signals, verify every claim"]:::rel
        CONF --> CRIT
    end

    DECIDE{"confident &amp;<br/>all claims verified?"}:::decide
    OUT[/"Ranked picks + score + explanation<br/>+ confidence + trust status"/]:::out
    HUMAN{{"Flag for human review<br/>(low confidence / unverified)"}}:::human

    subgraph VERIFY["Verification &mdash; tests/ + evaluate.py"]
        T["pytest suite (34 tests)"]:::test
        EV["evaluate.py &rarr; evaluation_results.md<br/>consistency &bull; self-critique rate<br/>avg confidence &bull; review rate &bull; genre bias"]:::test
    end

    U --> VP
    CSV --> VS
    VP --> SC1
    VS --> SC1
    RK --> CONF
    CRIT --> DECIDE
    DECIDE -->|yes| OUT
    DECIDE -->|no| HUMAN
    HUMAN --> OUT
    OUT --> U

    T -. asserts .-> SC1
    T -. asserts .-> CONF
    T -. asserts .-> CRIT
    EV -. measures .-> DECIDE

    classDef user fill:#e8f0fe,stroke:#4285f4,color:#111;
    classDef data fill:#e6f4ea,stroke:#34a853,color:#111;
    classDef guard fill:#fce8e6,stroke:#ea4335,color:#111;
    classDef rel fill:#fff0f6,stroke:#d5399b,color:#111;
    classDef decide fill:#fef7e0,stroke:#f9ab00,color:#111;
    classDef out fill:#f3e8fd,stroke:#a142f4,color:#111;
    classDef human fill:#e0f7fa,stroke:#00acc1,color:#111;
    classDef test fill:#f1f3f4,stroke:#5f6368,color:#111;
```

## Legend

| Layer | Component | Role |
|-------|-----------|------|
| Input | User taste profile + `data/songs.csv` | Preferences and the song catalog |
| Guardrails | `reliability.validate_*` | Reject bad profiles, quarantine bad rows |
| Core | `recommender.py` | Scores, ranks, and explains |
| Reliability | `reliability.score_confidence` / `critique_recommendation` | Confidence + self-critique |
| Decision | pipeline | Trust, or flag for human review |
| Verification | `tests/` + `evaluate.py` | Automated checks + reliability metrics |

_All components above are implemented. `pipeline.py` orchestrates the flow and
logs every stage._
