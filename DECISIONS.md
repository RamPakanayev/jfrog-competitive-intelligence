# DECISIONS.md — Architecture Decision Log

Every significant decision: the options we weighed, what we chose, and why. Newest at the bottom.

---

## ADR-001 · Overall approach
**Options:** (A) GenAI-enriched pipeline + dashboard · (B) RAG-chat-first tool · (C) autonomous research agents.
**Chosen:** A, with a thin chat slice as a last-priority stretch feature.
**Why:** The assignment's hard requirements are *daily updates* and *JFrog-vs-competitor comparison* — A satisfies both deterministically, demos reliably, and scales by config. B makes the daily-digest requirement awkward and its live quality is hard to guarantee. C is impressive but slow, expensive, and flaky in a live demo — it goes on the future roadmap instead.

## ADR-002 · Backend framework: FastAPI
**Options:** FastAPI · Flask · Django.
**Chosen:** FastAPI.
**Why:** async-native (concurrent feed fetching), Pydantic validation everywhere (we validate LLM structured outputs anyway), auto-generated OpenAPI docs (free credibility in review). Flask lacks native async/typing; Django is too heavy for a single-purpose API.

## ADR-003 · Frontend: React + TypeScript + Vite (explicitly not Next.js)
**Options:** Next.js · React+Vite · Streamlit · server-rendered HTMX.
**Chosen:** React 18 + TS + Vite + Tailwind + TanStack Query + recharts.
**Why:** An internal dashboard needs no SSR/SEO — Next.js adds complexity without benefit here (and user preference excluded it). Streamlit is fastest but looks generic and limits UI control — weak for a role where the UI is graded. Vite gives fast builds and a typed API contract.

## ADR-004 · LLM access: LiteLLM gateway
**Options:** direct Anthropic SDK · LiteLLM · LangChain.
**Chosen:** LiteLLM behind a thin internal `gateway.py`.
**Why:** Requirement: provider-generic (Anthropic, OpenAI, Gemini, **local Ollama**) switchable by env var. LiteLLM gives one interface + retries + cost tracking for all of them. LangChain is too heavy for three structured calls. Bonus defense: competitive-intel data is sensitive — the local-model option keeps it in-house.

## ADR-005 · Storage: SQLite + SQLAlchemy
**Options:** SQLite · Postgres (docker service) · JSON files.
**Chosen:** SQLite via SQLAlchemy 2.0.
**Why:** Zero-ops for reviewers, single file, plenty for this scale; SQLAlchemy makes Postgres a connection-string change (the scaling answer). A Postgres container would slow setup and add failure modes for zero demo value.

## ADR-006 · Chat retrieval: SQLite FTS5 (BM25), no vector DB
**Options:** ChromaDB embeddings · SQLite FTS5 · no chat at all.
**Chosen:** FTS5 BM25 behind a small retrieval interface; chat is a stretch feature built last.
**Why:** Originally Chroma was proposed; cut when challenged on necessity (YAGNI). At hundreds-to-thousands of short articles, BM25 retrieval quality is competitive with embeddings, with zero new dependencies, no model downloads, smaller image. The retrieval interface means pgvector/Chroma can slot in when the corpus grows. This decision demonstrates deliberate right-sizing — not ignorance of RAG.

## ADR-007 · Scheduling: APScheduler in-process
**Options:** APScheduler · OS cron · Celery beat · GitHub Actions cron.
**Chosen:** APScheduler inside the FastAPI process + manual POST /api/refresh.
**Why:** One process, no extra infra, visible in-app. At scale you'd move to a queue/orchestrator (documented in roadmap); for a single-node tool, in-process is honest engineering.

## ADR-008 · Packaging: Docker Compose, two services
**Options:** single container (FastAPI serves SPA) · two services (nginx + api) · no Docker.
**Chosen:** docker-compose with `web` (nginx serving built SPA, proxying /api) + `api` (uvicorn); non-Docker dev path documented.
**Why:** `docker compose up` is the friendliest reviewer experience; two services mirror production topology (separation of concerns) while staying one command.

## ADR-009 · Competitors, matrix, capability sheet as YAML config
**Options:** database + admin UI · YAML in repo.
**Chosen:** YAML (`competitors.yaml`, `feature_matrix.yaml`, `jfrog_capabilities.yaml`).
**Why:** Config-as-code: adding a competitor is a reviewable PR, not a UI feature we'd have to build. Factual claims (matrix, JFrog capabilities) stay human-curated — the governance answer to "how do you stop the LLM inventing JFrog features?"

## ADR-010 · Keyless demo mode with bundled seed data
**Options:** require API keys · live-fetch on first run · bundled precomputed dataset.
**Chosen:** auto-detected demo mode loading `data/demo/seed.json`.
**Why:** The single biggest demo risk is a reviewer cloning the repo, having no keys, and seeing an empty app. Bundled data guarantees a populated UI in minutes; a banner keeps it honest.

## ADR-011 · Grounding & citation policy
**Options:** free-form LLM prose · structured outputs with enforced citations.
**Chosen:** all generated content is schema-validated JSON where each claim carries `article_ids`; entries with invalid/missing ids are dropped; Delta analysis may only cite JFrog capabilities from the curated sheet; battlecards visually separate "curated" from "generated (cited)" zones.
**Why:** Interview-critical: "GenAI synthesizes and structures; every claim traces to a timestamped ground-truth source; facts humans curate."

## ADR-012 · Project name: Ribbit
**Options:** Periscope · LilyPad · PondWatch · Spyglass · Frogman · Ribbit.
**Chosen:** Ribbit.
**Why:** User wanted frog/swamp flavor. A ribbit is the frog's broadcast signal — this tool broadcasts the daily signal from the swamp (the DevOps market). Short, memorable, on-brand for JFrog.

## ADR-013 · Domain-tuned taxonomy (two dimensions)
**Options:** single "category" field · domain × event-type dimensions.
**Chosen:** `domain` (artifact_management, container_registry, devsecops_scanning, cicd, sbom_supply_chain, other) × `event_type` (product_launch, feature_update, security_advisory, pricing_change, funding_ma, partnership, other).
**Why:** External review (Gemini) flagged generic-news noise as the top quality risk. Two orthogonal dimensions make the relevance gate strict and the feed filterable the way a CI analyst actually thinks ("show me all *pricing* moves in *artifact management*").

## ADR-014 · Test imports resolve via `pythonpath` in pytest.ini
**Options:** run tests as `python -m pytest` everywhere · add `backend/tests/__init__.py` to make tests a package · set `pythonpath = .` in `backend/pytest.ini`.
**Chosen:** `pythonpath = .` in `backend/pytest.ini`.
**Why:** With pytest's default prepend import mode and no `__init__.py` in `tests/`, pytest puts `tests/` (not `backend/`) on `sys.path`, so `import app` fails under the bare `pytest` command. `python -m pytest` masks it by inserting the cwd, but that quietly changes the documented command for every contributor and for CI. `pythonpath = .` fixes the root cause in one line, keeps `pytest` working from `backend/`, and avoids turning the test directory into an importable package (which would invite accidental cross-test imports). Surfaced by the Task-1 implementer during the first TDD cycle.

## ADR-015 · API keys typed as `SecretStr`
**Options:** plain `str` fields · `pydantic.SecretStr` · a separate secrets loader.
**Chosen:** `SecretStr` for `anthropic_api_key`, `openai_api_key`, `gemini_api_key`, `tavily_api_key`; `.get_secret_value()` at the two call sites that need the raw value (LLM gateway, Tavily adapter).
**Why:** The `Settings` object is passed through the pipeline, gateway, and API layers, so any stray `repr()`, debug log, or exception traceback would print live keys in plaintext. `SecretStr` masks them by default and forces an explicit, greppable unwrap where the value is genuinely needed. Caught in code review while the change still cost four lines and zero call sites — a separate secrets loader would be over-engineering for a tool that reads keys from env/`.env`.

## ADR-016 · Datetimes stored via a `UtcDateTime` type decorator
**Options:** normalize timezone at each call site · `DateTime(timezone=True)` · a `UtcDateTime` `TypeDecorator` · store epoch integers.
**Chosen:** a `TypeDecorator` that binds aware datetimes as naive UTC and returns every value timezone-aware.
**Why:** SQLite has no native datetime type and discards tzinfo, so values written as aware UTC read back naive — invisible within a single session because SQLAlchemy's identity map returns the original object. The consequence was not just `TypeError` on comparisons: the API serializes these columns with `.isoformat()`, and an offset-less string is parsed by browsers as *local* time, shifting every timestamp in the UI and moving near-midnight items to the wrong day. `DateTime(timezone=True)` does not help on SQLite (the dialect still drops the offset), and per-call-site normalization is a rule everyone must remember forever. One type, applied to six columns, makes the storage layer honest instead.

## ADR-017 · Ingest commits per item, not per batch
**Options:** one commit per batch (simplest) · savepoint per item · commit per item with `IntegrityError` tolerance · a global ingest lock.
**Chosen:** commit per item, catching `IntegrityError` to skip an item another writer already inserted.
**Why:** Dedupe pre-checks the database, but a check-then-insert is a race: the architecture deliberately allows a manual "Refresh now" to overlap the scheduled daily run. Under one commit per batch, a single lost race raises an unhandled `IntegrityError` and rolls back *the entire batch* — verified in a two-session reproduction, where an unrelated valid article was lost alongside the duplicate. Losing one duplicate is correct; losing the rest of the day's news because of it is not. Per-item commits also mean a crash mid-run keeps the work already done. At this volume (~150 items/day) the extra commits cost nothing measurable, which is why the simpler batch commit isn't worth defending.

## ADR-019 · The executive summary is labelled synthesis, not a cited claim
**Options:** give `exec_summary` its own `article_ids` and enforce them · drop the field · constrain it by prompt and label it in the UI.
**Chosen:** constrain by prompt (it may only synthesize facts already stated in the cited sections, introducing no new company, product, number, date or event) and mark it `AI SYNTHESIS` in the dashboard.
**Why:** Adversarial testing of the citation firewall found that `exec_summary` is bare prose with no `article_ids` field, so no code path can validate it — a summary reading "Snyk raised $500M and JFrog is doomed" survives untouched even when zero articles have been ingested. That is the most-read line on the dashboard, so leaving the gap silent would have undermined the whole "every claim traces to a source" story. Attaching citations to a summary-of-summaries is the wrong shape (its job is prioritization across claims, not asserting new facts), and dropping it would cost the feature executives actually read. Constraining it and being visibly honest about what it is holds the line the enforcement code cannot.

## ADR-018 · Dedupe matches on canonical URL OR content hash
**Options:** URL only · content hash only · both, ANDed · both, ORed.
**Chosen:** OR — an item is a duplicate if either its canonicalized URL or its content hash (title + excerpt) already exists.
**Why:** The same story genuinely arrives by several routes: a vendor's own feed, Hacker News linking the same URL with tracking parameters attached, and a syndicated copy on a different domain entirely. URL canonicalization catches the first two; only the content hash catches the third, since the syndicated copy shares no URL. Requiring both to match (AND) would let every syndicated copy through, which is the common case for the wire-service items these feeds carry. Measured coverage of the URL half: trailing slashes, fragments, empty queries and tracking parameters all collapse correctly; scheme drift (`http`/`https`), `www` vs apex, and reordered query parameters do not — those are left to the content hash on purpose, because normalizing scheme or parameter order can merge genuinely different pages.
