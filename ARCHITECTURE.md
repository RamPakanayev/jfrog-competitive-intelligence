# ARCHITECTURE.md — Ribbit

Living document: diagrams are kept in sync with the implementation. Rendered natively by GitHub (Mermaid).

## 1. System context

```mermaid
flowchart LR
    subgraph SRC[Data sources]
        RSS[RSS/Atom<br/>competitor blogs & release notes]
        HN[Hacker News<br/>Algolia API]
        GN[Google News RSS<br/>third-party coverage per competitor]
        IND[Industry feeds<br/>CNCF · The New Stack · DevOps.com · SD Times]
        TV[Tavily search<br/>optional key]
    end

    subgraph API[FastAPI backend]
        ADP[Source adapters]
        PIPE[Pipeline<br/>dedupe → enrich → delta → digest → battlecards]
        DB[(SQLite + FTS5)]
        SCH[APScheduler<br/>daily @ REFRESH_HOUR]
    end

    subgraph LLMGW[LiteLLM gateway]
        ANT[Anthropic]
        OLL[Ollama local]
        OTH[OpenAI / Gemini]
    end

    UI[React + TS dashboard<br/>Today · Feed · Competitors · Compare]
    CFG[[YAML config<br/>competitors · matrix · JFrog capabilities]]

    SRC --> ADP --> PIPE --> DB
    SCH --> ADP
    PIPE <--> LLMGW
    CFG --> PIPE
    UI <-->|REST /api| API
```

Notes:
- The FTS5 table already backs the Feed tab's search box today. An analyst-chat tab with its
  own BM25-ranked retrieval module was designed (ADR-006) but not built in this pass — see the
  roadmap in README.md.
- Reddit was removed as a source after a live run showed it returns 403 to unauthenticated
  clients; Google News RSS replaced it and restored third-party coverage (ADR-024, ADR-026).
  The Reddit adapter and its tests remain in the codebase, disabled by config.
- 20 sources total, all keyless: per competitor a vendor blog feed + a Hacker News query + a
  Google News query, plus the four industry feeds. Tavily is optional and only used if a key
  is present.

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
    P->>D: record source_runs (health, per source, before dedupe)
    P->>P: canonicalize URL + hash → dedupe
    Note over P,L: enrich → delta → digest → battlecards run inside a worker thread<br/>(asyncio.to_thread, own DB session) so the API event loop stays<br/>responsive to concurrent requests during a multi-minute refresh (ADR-021)
    loop each new item
        P->>L: enrich (structured JSON)
        L-->>P: relevant, competitors, domain, event_type,<br/>summary, jfrog_impact, so_what
        alt jfrog_impact >= 3 (DELTA_THRESHOLD, calibrated on a live run — ADR-023)
            P->>L: delta analysis (grounded in capability sheet)
            L-->>P: move, jfrog_equivalent, impact, talking points
        end
        P->>D: save article + enrichment (+ FTS index)
    end
    P->>L: compose daily digest (citations enforced)
    L-->>D: digest with article_ids per claim
    P->>L: refresh battlecard recent-moves per competitor
    L-->>D: cited recent moves
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
- **LLM stages off the event loop**: the four LLM-touching stages run via `asyncio.to_thread`
  on their own DB session, separate from the fetch/insert session (ADR-021); the pipeline
  also refuses to start a second run while one is already in progress (ADR-022).
- **No vector database anywhere**: retrieval is SQLite FTS5 — already powering the Feed
  tab's search box. A dedicated BM25-ranked retrieval module for an analyst-chat tab was
  designed (ADR-006) but is not built; it is a roadmap item, not a shipped diagram box.
