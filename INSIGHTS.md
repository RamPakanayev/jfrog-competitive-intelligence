# INSIGHTS.md — Ribbit

Running log of insights, challenges, and learnings gathered while building Ribbit. Feeds the README's "challenges & pitfalls" section and the interview presentation. Newest at the bottom.

---

## 2026-08-03 — Design phase

1. **YAGNI beats résumé-driven design.** The first draft included a vector database (Chroma) for RAG chat. When challenged with "is RAG even necessary?", the honest answer was no: at hundreds-to-thousands of short articles, SQLite FTS5 (BM25) retrieval is competitive with embeddings and adds zero dependencies. Cutting it simplified the image, the setup, and the story. Being able to explain *why you didn't use* a technology is as valuable as using it.

2. **The biggest demo risk isn't the AI — it's an empty screen.** A reviewer without API keys would see a blank dashboard. Bundling a precomputed demo dataset (auto-loaded when no LLM is available) turns the worst failure mode into a non-event.

3. **Noise is the real enemy of competitive intelligence.** External review (Gemini) confirmed the top quality risk: generic tech-news pollution ("Microsoft announces AI thing" ≠ CI signal). Countermeasures: domain-curated sources, a strict LLM relevance gate, and a two-dimensional taxonomy (domain × event type) instead of one vague "category".

4. **Hallucination defense must be structural, not aspirational.** Three concrete mechanisms instead of "we prompt it to be truthful": (a) every generated claim carries `article_ids`, schema-enforced, invalid claims dropped; (b) Delta analysis may only reference JFrog capabilities from a human-curated YAML sheet; (c) the feature matrix is entirely human-curated — the LLM never asserts uncited facts about JFrog or competitors.

5. **A second AI reviewer is a cheap red team.** Running the design past another model surfaced the domain-precision gap and the "dynamic vs static comparison" gap (which became Delta analysis) before any code was written.

6. **Config-as-code keeps the tool alive after the demo.** Competitors, sources, matrix, and capability sheet live in YAML: adding competitor #6 is a pull request, not a feature request.

## 2026-08-03 — Implementation phase

7. **A green test suite can still be lying.** Two guards added to the config tests only counted once we deliberately broke the YAML (renamed `notes:` → `note:`, dropped a vendor from the matrix) and watched them fail. Mutation-testing a new assertion takes a minute and is the difference between a test that guards something and a test that decorates the file.

8. **SQLite silently drops timezones, and the damage surfaces in the browser.** Datetimes written as aware UTC read back naive from a fresh session — invisible inside one session because SQLAlchemy's identity map hands back the original Python object. The real damage was downstream: the API serializes with `.isoformat()`, and an offset-less string like `2026-08-03T08:39:41` is parsed by JavaScript as *local* time, shifting every timestamp in the UI and pushing near-midnight items onto the wrong day. Fixed once in a `UtcDateTime` `TypeDecorator` rather than at a dozen call sites. Found only because the task explicitly asked "check what comes back in a fresh session" — the three passing tests never touched a fresh read.

9. **"Fails loudly" has to be checked, not assumed.** The source adapters were designed to raise on failure so the orchestrator could mark a feed unhealthy. They did — for HTTP errors. A feed returning `200 OK` with truncated XML parsed to zero entries and returned quietly, which the health panel would have shown as a healthy source having a slow news day. The fix distinguishes "unparseable and empty" from the very common case of a slightly malformed feed that still yields entries; over-correcting there would have silently dropped working sources.

10. **Silent duplicate-collapse is the nastiest failure mode in an ingest pipeline.** Two separate instances: Reddit posts missing a `permalink` all resolved to the bare domain, and once one such row existed every future permalink-less post matched it forever; and whitespace-only URLs all canonicalized to the same `https:///` sentinel. In both cases the pipeline reported success while quietly discarding real stories. Nothing crashes, nothing logs, and the only symptom is a digest that feels thin.

11. **`.replace(tzinfo=utc)` is not a conversion.** Applied to an already-aware timestamp it relabels the instant rather than converting it, so a `10:00+02:00` publication was stored as `10:00Z` — off by the offset, silently, forever. The correct form branches: convert when aware, assume UTC only when naive.

12. **The most valuable review findings were about what wasn't there.** Spec review confirms the code matches the plan; the findings that actually improved the system came from asking what the code fails to do — untested grounding text, two config files with nothing tying them together, secrets typed as plain strings. Verification catches deviation; adversarial questions catch design gaps.
