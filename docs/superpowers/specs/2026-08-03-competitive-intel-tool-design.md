# Ribbit — Competitive Intelligence for JFrog: Design Spec

**Date:** 2026-08-03 · **Status:** Approved pending user review · **Stage:** JFrog home assignment, Stage 1

## 1. Problem & goals

JFrog's Competitive Intelligence (CI) team needs to stay on top of a daily-shifting landscape: what competitors ship, announce, price, and break — and what each move means for JFrog. Today that means manually reading many scattered sources.

**Ribbit** is a GenAI-powered pipeline + dashboard that:

1. Ingests news daily from curated, domain-specific sources per competitor.
2. Uses an LLM to filter noise and enrich each item with CI-relevant structure (who, what domain, what kind of event, how much it matters to JFrog, and the one-line "so what").
3. Generates a daily executive digest and per-competitor battlecards — **every generated claim linked to its source**.
4. Shows how JFrog compares to competitors: a human-curated feature matrix plus automated "Delta analysis" of high-impact competitor moves.

### Goals
- A reviewer clones the repo, runs `docker compose up`, and sees a **populated, working app within ~2 minutes with zero API keys** (demo mode).
- With keys configured: a scheduled daily refresh keeps the dashboard current unattended.
- Every LLM-generated claim in digests/battlecards traces to a timestamped source link.
- Every technology choice has a recorded rationale (DECISIONS.md) — the user must defend all choices in an interview.

### Non-goals (v1 — listed as future roadmap in README)
- Autonomous browsing/research agents; vector database; Slack/email delivery; authentication/multi-tenancy; human-review workflow UI; historical backfill beyond the seed window; mobile layout polish.

## 2. Architecture

```
ribbit/
├── backend/               # FastAPI app (Python 3.12)
│   ├── app/
│   │   ├── main.py        # FastAPI entry, routers, scheduler startup
│   │   ├── config.py      # env + YAML config loading (pydantic-settings)
│   │   ├── models.py      # SQLAlchemy models + FTS5 setup
│   │   ├── sources/       # one adapter per source type: rss.py, hackernews.py, reddit.py, tavily.py
│   │   ├── pipeline/      # fetch.py, dedupe.py, enrich.py, delta.py, digest.py, battlecard.py, run.py
│   │   ├── llm/           # gateway.py (LiteLLM wrapper), schemas.py (Pydantic structured outputs), prompts.py
│   │   ├── retrieval/     # search.py (FTS5 BM25 interface — future: pgvector impl)
│   │   ├── api/           # routers: articles, digest, competitors, matrix, chat, admin (refresh/health)
│   │   └── demo.py        # demo-mode detection + seed loading
│   └── tests/
├── frontend/              # React 18 + TypeScript + Vite + Tailwind + TanStack Query + react-router + recharts
│   └── src/{pages,components,api,types}
├── config/
│   ├── competitors.yaml       # tracked competitors + their sources + battlecard curated base
│   ├── jfrog_capabilities.yaml# curated JFrog capability sheet (grounds Delta analysis)
│   ├── feature_matrix.yaml    # curated JFrog-vs-competitor matrix
│   └── industry_feeds.yaml    # non-competitor domain feeds (CNCF, The New Stack, InfoQ DevOps, DevOps.com)
├── data/demo/seed.json    # bundled dataset: articles + enrichments + digests + battlecards (keyless demo)
├── docker-compose.yml     # web (nginx serving built SPA, proxies /api) + api (uvicorn); volume for SQLite
├── DECISIONS.md           # living ADR log
├── ARCHITECTURE.md        # living diagrams doc (Mermaid)
├── INSIGHTS.md            # living log of challenges/learnings
└── README.md              # setup, screenshots, now-vs-future, challenges
```

**Stack rationale (summary — full ADRs in DECISIONS.md):** FastAPI (async fetching, Pydantic, auto OpenAPI); React+Vite+TS per user preference (no SSR need → not Next.js); LiteLLM gateway for provider-agnostic LLM access (Anthropic default, Ollama local, OpenAI/Gemini supported — sensitive CI data can stay in-house); SQLite + SQLAlchemy (zero-ops demo, Postgres is a config swap); FTS5 BM25 retrieval instead of a vector DB (right-sized for corpus scale); Docker Compose for one-command review.

## 3. Configuration

### competitors.yaml (shape)
```yaml
competitors:
  - slug: sonatype
    name: Sonatype
    color: "#79b62f"
    sources:
      rss: ["https://www.sonatype.com/blog/rss.xml", ...]
      hn_query: "sonatype OR \"nexus repository\""
      reddit: {subreddits: ["devops"], query: "sonatype OR nexus"}
      tavily_query: "Sonatype news"          # used only if TAVILY_API_KEY set
    battlecard_base:                          # human-curated, no citations required
      strengths: ["Deep Maven-ecosystem roots", ...]
      weaknesses: [...]
      how_jfrog_wins: [...]
  # gitlab, github, docker, snyk — same shape
```

Demo set: **Sonatype, GitLab, GitHub, Docker, Snyk** (core rivals across artifact management + DevSecOps). Adding a competitor = one YAML block, no code.

### Environment (.env.example)
```
LLM_PROVIDER=anthropic            # anthropic | openai | gemini | ollama
LLM_MODEL=claude-haiku-4-5        # any LiteLLM model id; cheap default
ANTHROPIC_API_KEY=                # or OPENAI_API_KEY / GEMINI_API_KEY
OLLAMA_BASE_URL=http://host.docker.internal:11434
LLM_FALLBACK_PROVIDER=ollama      # optional fallback chain
TAVILY_API_KEY=                   # optional broader news search
REFRESH_HOUR=07                   # daily run, local time
DEMO_MODE=auto                    # auto | on | off
```

## 4. Data model (SQLite via SQLAlchemy)

- **articles**: id, url (canonical, unique), content_hash (unique), title, body_excerpt, source_name, source_type, published_at, fetched_at, status(new|enriched|irrelevant|failed)
  - enrichment columns: relevant, competitors (json), domain, event_type, summary, jfrog_impact (1–5), so_what, enriched_at
  - delta columns (nullable, only when jfrog_impact ≥ 4): delta_move, delta_jfrog_equivalent, delta_strategic_impact (high|medium|low), delta_talking_points (json)
- **articles_fts**: FTS5 virtual table (title, body_excerpt, summary) kept in sync by triggers — powers chat retrieval and feed search.
- **digests**: date (unique), exec_summary, sections (json: top_developments, by_competitor, threats_opportunities — every entry carries `article_ids`), generated_at, model_used
- **battlecards**: competitor_slug, recent_moves (json, citation-carrying), generated_at (curated base comes from YAML at read time)
- **source_runs**: run_id, source_name, started_at, ok, items_found, error — powers the source-health panel.

Taxonomy enums — **domain**: artifact_management, container_registry, devsecops_scanning, cicd, sbom_supply_chain, other · **event_type**: product_launch, feature_update, security_advisory, pricing_change, funding_ma, partnership, other.

## 5. Pipeline (fetch → dedupe → enrich → delta → digest → battlecards)

Triggered by APScheduler daily at REFRESH_HOUR and by POST /api/refresh. Stages:

1. **Fetch** — all adapters run concurrently (asyncio); each is isolated: one source failing logs a source_run error and the run continues. Window: items newer than N days (default 2; seed capture uses 14). Adapters use feed/API-provided text only (title + summary/content fields) — **no full-page scraping in v1** (robots.txt/paywall complexity is deferred to the roadmap; enrichment quality on feed excerpts is sufficient for classification and summarization).
2. **Dedupe** — canonical URL (strip tracking params) + content hash; skip existing.
3. **Enrich** — per new item, ONE structured LLM call (Pydantic-validated JSON): `{relevant, competitors[], domain, event_type, summary ≤2 sentences, jfrog_impact 1–5, so_what}`. Strict relevance gate: must concern a tracked competitor or the software-supply-chain domain; generic vendor news is marked irrelevant and hidden. Prompt includes taxonomy definitions + few-shot examples. Results cached by content_hash (re-runs are free). Malformed JSON → one repair-prompt retry → else status=failed (item still visible, unenriched).
4. **Delta analysis** — items with jfrog_impact ≥ 4 get a second call: `{competitor_move, jfrog_equivalent, strategic_impact, talking_points[≤3]}`. The prompt receives the **curated jfrog_capabilities.yaml** — the model may only reference JFrog capabilities from that sheet (anti-hallucination grounding).
5. **Digest** — one call composes the day's brief from enriched items (ids + summaries in prompt): exec_summary, top developments, by-competitor highlights, threats & opportunities. **Every entry must carry article_ids** — enforced by schema validation; entries without valid ids are dropped.
6. **Battlecards** — per competitor, refresh "recent moves & signals" from that competitor's recent enriched items (citation-carrying, same enforcement). Curated base (strengths/weaknesses/how-JFrog-wins) renders from YAML — clearly labeled "curated" in the UI vs "generated" with links.

**LLM gateway** (`llm/gateway.py`): thin wrapper over LiteLLM — provider/model from env, retries with backoff, optional fallback provider, token/cost logging per run. Estimated cost: ~50–150 enrichment calls/day on a small model ≈ cents/day; zero on Ollama.

## 6. API surface (REST, JSON)

- `GET /api/digest?date=` — digest for date (default: latest)
- `GET /api/articles?competitor=&domain=&event_type=&min_impact=&q=&page=` — feed with filters (q uses FTS5)
- `GET /api/competitors` — list + profile summary stats
- `GET /api/competitors/{slug}/battlecard` — curated base + generated recent moves
- `GET /api/matrix` — feature matrix from YAML
- `POST /api/chat` `{question}` → `{answer, citations[{article_id,title,url,published_at}]}` — FTS5 top-k retrieval → LLM synthesis; answers only from retrieved articles; refuses gracefully when nothing relevant is found
- `POST /api/refresh` / `GET /api/refresh/status` — trigger + poll pipeline progress (stage, counts, errors)
- `GET /api/sources/health` — last run per source
- `GET /api/meta` — provider in use, demo-mode flag, last refresh, version

## 7. Frontend (5 tabs + status strip)

1. **Today** — daily digest with KPI cards (new items, high-impact count, most-active competitor), each claim's sources as clickable timestamped chips; date picker for history.
2. **Feed** — filterable list (competitor, domain, event type, min impact, text search); cards show summary, so-what, impact badge, Delta panel when present, source link.
3. **Competitors** — profile cards → battlecard (curated zone visually distinct from generated zone with citations).
4. **Compare** — feature matrix table (JFrog vs selected competitors) + recharts radar chart.
5. **Chat** (stretch, built last) — "ask the analyst" over ingested corpus, numbered citations linking to sources; hidden with an explainer when no LLM is available.

Status strip: last refresh, LLM provider badge, demo-mode banner, source-health dot, Refresh Now button (disabled in demo mode with tooltip).

## 8. Demo mode & error handling

- **Demo mode (auto)**: on startup, if no usable LLM provider (no key, Ollama unreachable) → load `data/demo/seed.json` (articles with precomputed enrichments, digests, battlecards captured during development) into SQLite. UI shows demo banner. Reviewer sees a fully populated app with zero setup. `DEMO_MODE=off` forces live mode.
- Per-source isolation + source-health panel (partial data beats no data).
- LLM: retry w/ backoff → fallback provider → graceful degradation (unenriched items visible; digest regenerable via refresh).
- All generated content schema-validated; citation ids verified to exist before save.

## 9. Testing & CI

- **pytest**: adapters against recorded fixture payloads (no network); dedupe/canonicalization; enrichment parsing incl. malformed-JSON repair path (mocked LLM); digest citation-enforcement; API endpoints via TestClient in demo mode.
- **Frontend**: vitest on 2–3 key components; `tsc --noEmit` + build in CI.
- **GitHub Actions**: lint (ruff, eslint) + tests + docker build on PR/push.

## 10. Build order (lean loop first; ~5 days, leaving Stage-2 time)

1. **Day 1**: scaffold, config loading, models, RSS+HN adapters, dedupe, LLM gateway, enrichment — end-to-end via CLI into SQLite.
2. **Day 2**: Reddit adapter, delta, digest, battlecards, REST API, scheduler, demo-seed capture.
3. **Day 3**: frontend shell + Today + Feed + status strip + refresh flow.
4. **Day 4**: Competitors + Compare tabs, Tavily (optional), polish, screenshots, README.
5. **Day 5**: tests/CI hardening, **chat (stretch)**, demo video, buffer.

Docs trio (DECISIONS/ARCHITECTURE/INSIGHTS) updated continuously throughout.

## 11. Known risks & mitigations (seed for INSIGHTS.md)

- **Relevance precision** is the product: tune the gate with few-shot examples; strict > broad (noise kills CI tools).
- **Feed availability/format drift**: adapters tolerant (feedparser), isolated failures, recorded fixtures for tests.
- **Reddit/HN rate limits & UA policies**: proper User-Agent, modest windows, backoff.
- **LLM JSON validity**: Pydantic validation + repair retry + fail-soft.
- **Hallucination**: citation enforcement by schema; curated capability sheet grounds JFrog claims; matrix human-curated.
- **Time**: chat is explicitly cuttable; core loop lands by Day 2.

## 12. Success criteria

- [ ] `docker compose up` → populated UI at :3000 in ≤2 min, no keys.
- [ ] With a key: POST /api/refresh ingests real items and regenerates the digest; scheduler fires daily.
- [ ] Every digest/battlecard claim shows ≥1 clickable, timestamped source.
- [ ] Provider swap = env-var change (demonstrate Anthropic ↔ Ollama).
- [ ] CI green; README covers setup, now-vs-future, challenges.
