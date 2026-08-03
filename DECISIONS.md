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
