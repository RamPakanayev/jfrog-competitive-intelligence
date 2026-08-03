# ARCHITECTURE.md — Ribbit

Living document: diagrams are kept in sync with the implementation. Rendered natively by GitHub (Mermaid).

## 1. System context

```mermaid
flowchart LR
    subgraph SRC[Data sources]
        RSS[RSS/Atom<br/>competitor blogs & release notes]
        HN[Hacker News<br/>Algolia API]
        RD[Reddit JSON]
        IND[Industry feeds<br/>CNCF · The New Stack · InfoQ]
        TV[Tavily search<br/>optional key]
    end

    subgraph API[FastAPI backend]
        ADP[Source adapters]
        PIPE[Pipeline<br/>dedupe → enrich → delta → digest → battlecards]
        DB[(SQLite + FTS5)]
        SCH[APScheduler<br/>daily @ REFRESH_HOUR]
        RET[Retrieval<br/>FTS5 BM25]
    end

    subgraph LLMGW[LiteLLM gateway]
        ANT[Anthropic]
        OLL[Ollama local]
        OTH[OpenAI / Gemini]
    end

    UI[React + TS dashboard<br/>Today · Feed · Competitors · Compare · Chat]
    CFG[[YAML config<br/>competitors · matrix · JFrog capabilities]]

    SRC --> ADP --> PIPE --> DB
    SCH --> ADP
    PIPE <--> LLMGW
    CFG --> PIPE
    UI <-->|REST /api| API
    RET --> DB
```

## 2. Daily pipeline sequence

```mermaid
sequenceDiagram
    participant S as Scheduler / Refresh button
    participant A as Adapters (concurrent)
    participant P as Pipeline
    participant L as LLM (via LiteLLM)
    participant D as SQLite

    S->>A: run(window = 2 days)
    A->>P: raw items (per-source isolation)
    P->>P: canonicalize URL + hash → dedupe
    loop each new item
        P->>L: enrich (structured JSON)
        L-->>P: relevant, competitors, domain, event_type,<br/>summary, jfrog_impact, so_what
        alt jfrog_impact >= 4
            P->>L: delta analysis (grounded in capability sheet)
            L-->>P: move, jfrog_equivalent, impact, talking points
        end
        P->>D: save article + enrichment (+ FTS index)
    end
    P->>L: compose daily digest (citations enforced)
    L-->>D: digest with article_ids per claim
    P->>L: refresh battlecard recent-moves per competitor
    L-->>D: cited recent moves
    P->>D: record source_runs (health)
```

## 3. Data model

```mermaid
erDiagram
    ARTICLES ||--o{ DIGEST_CLAIMS : cited_by
    ARTICLES {
        int id PK
        string url UK "canonical"
        string content_hash UK
        string title
        text body_excerpt
        string source_name
        datetime published_at
        string status "new|enriched|irrelevant|failed"
        bool relevant
        json competitors
        string domain
        string event_type
        string summary
        int jfrog_impact "1-5"
        string so_what
        string delta_move "nullable"
        string delta_jfrog_equivalent "nullable"
        string delta_strategic_impact "nullable"
        json delta_talking_points "nullable"
    }
    DIGESTS {
        date date UK
        text exec_summary
        json sections "claims carry article_ids"
        datetime generated_at
        string model_used
    }
    BATTLECARDS {
        string competitor_slug
        json recent_moves "citation-carrying"
        datetime generated_at
    }
    SOURCE_RUNS {
        int run_id
        string source_name
        datetime started_at
        bool ok
        int items_found
        string error
    }
    DIGEST_CLAIMS["(claims live inside DIGESTS.sections JSON)"]
```

Note: competitors, the feature matrix, and the JFrog capability sheet are **YAML config**, not database tables (ADR-009).

## 4. Deployment

```mermaid
flowchart TB
    subgraph host[Reviewer machine — docker compose up]
        subgraph web[web container]
            NG[nginx :3000<br/>serves built SPA<br/>proxies /api → api:8000]
        end
        subgraph apic[api container]
            UV[uvicorn :8000<br/>FastAPI + APScheduler]
        end
        VOL[(named volume<br/>SQLite db + demo seed)]
        NG --> UV --> VOL
    end
    BROWSER[Browser :3000] --> NG
    KEYS{{.env: LLM keys optional<br/>none → demo mode}} -.-> UV
```

## 5. Key flows to remember

- **Demo mode**: no usable LLM at startup → seed `data/demo/seed.json` → banner in UI; Refresh disabled.
- **Citation enforcement**: digest/battlecard JSON is schema-validated; claims without existing `article_ids` are dropped before save.
- **Provider swap**: `LLM_PROVIDER`/`LLM_MODEL` env vars only — no code change (ADR-004).
