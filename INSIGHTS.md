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
