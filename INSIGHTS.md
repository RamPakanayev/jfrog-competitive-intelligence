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

## 2026-08-03 — Delivery pass (Task 24)

13. **Scope note, stated plainly:** this pass did not run the pipeline against a real
    Anthropic key (Task 24 Steps 1-2 — live refresh + `capture_seed.py`) because no key
    was available to the implementer. `data/demo/seed.json` is unchanged: the original 3
    hand-written sample articles, not a live capture. The README says exactly that rather
    than implying otherwise — the honest version of this log is worth more than a tidier
    one.
14. **The keyless reviewer path was verified for real, not assumed.** `docker compose up
    --build -d` with no `.env` file present, then a true `--no-cache` rebuild (no shared
    Docker layer cache) timed at ~30s on the verifying machine. All four tabs — Today,
    Feed, Competitors (list + a battlecard detail page), Compare — loaded populated data
    with zero browser console errors and nothing but `200 OK` in the API container log.
    The four README screenshots are real captures from that running stack, not mockups.
15. **Diagrams rot exactly where the plan and the shipped code part ways, and nobody
    notices until someone compares them side by side.** ARCHITECTURE.md had drifted from
    the implementation in three places by delivery time, none of them caught until this
    pass: the system-context diagram listed a "Chat" tab and a dedicated FTS5-retrieval
    component that Task 25 (stretch) never actually shipped; the pipeline sequence
    diagram didn't show that the four LLM stages run inside a worker thread
    (`asyncio.to_thread`, ADR-021) rather than inline on the API's event loop; and that
    same diagram recorded `source_runs` health rows as the *last* step of a refresh, when
    the code actually writes them right after fetching, before dedupe. All three are
    fixed now. None would have been caught by re-reading the diagram in isolation — only
    by re-deriving it from the code that was actually shipped.

## 2026-08-03 — First live run against a real LLM

16. **Nothing that mattered was found by the test suite.** 72 tests passed before the first
    live run, and the run still surfaced four real problems within minutes: Reddit blocking
    every request, a dead feed, a feature that never fired, and a test suite reading a real
    API key. Tests prove the code does what you told it to; only real data tells you whether
    what you told it was right.

17. **The relevance gate is the product.** 139 articles fetched, 109 discarded as noise — 78%.
    The discarded set was exactly right: HN "Show HN" posts, a DevOps jobs listicle, generic
    Copilot news. Getting that wrong in either direction ruins the tool: too loose and it's a
    spam feed, too strict and it misses the move that mattered.

18. **A threshold guessed before seeing data was wrong, and silently so.** Delta analysis
    was gated at impact ≥ 4. On real news the maximum score awarded was 3, so the feature
    produced nothing at all — no error, no warning, just an empty section that looked like
    "quiet day". Vendor blogs publish incremental news; "significant threat" is rare.
    Recalibrating to 3 turned zero deltas into seven (ADR-023). The lesson is not the number
    — it is that a magic constant chosen in a planning document deserves to be re-derived
    from the first real dataset.

19. **Sources rot in more than one way.** Reddit returns 403 to unauthenticated clients now,
    which is loud and easy to spot. InfoQ's DevOps feed returns a cheerful `200 OK` whose
    newest entry is from 2022 — silent, and indistinguishable from "quiet week" unless you
    look at the dates. Meanwhile Sonatype, Snyk and GitHub returned zero items for a
    completely legitimate reason: nothing published inside the 2-day window. Three
    identical-looking symptoms, three different causes.

20. **Debugging can leak what you are protecting.** Chasing the credential-isolation bug, I
    printed `get_secret_value()` to a terminal and exposed a live API key that then had to be
    rotated. The irony is instructive: the codebase already used `SecretStr` specifically so
    keys could never surface in a repr or a log, and the leak came from deliberately
    unwrapping that protection to debug. Redact at the point of debugging, not just in the
    application.

21. **Removing a broken source is only half the fix.** Dropping Reddit left every competitor
    covered by their own blog plus Hacker News — i.e. mostly vendors talking about
    themselves, which is precisely the wrong input for competitive intelligence. The
    replacement (Google News RSS search, keyless) restored the outside perspective and
    doubled the relevant-article count from 30 to 64, and delta analyses from 7 to 20.
    Worth noticing that the *shape* of the gap mattered more than the count: what was
    missing was third-party coverage, not volume.

22. **The boring abstraction paid for itself.** Adding a whole new class of source cost a
    URL-builder function and one config key, because Google News is just RSS and the RSS
    adapter never knew or cared where its feed came from. Every hour spent keeping adapters
    dumb bought this back.

23. **Sources fail in three different disguises.** Across two live runs: Reddit's JSON
    endpoint returns a loud `403`; Reddit's RSS endpoint returns a quiet `200` with zero
    entries; InfoQ returns `200` with real entries whose newest is from 2022; Security
    Boulevard returns `403` to the app's User-Agent while answering a hand-issued request
    fine; and Sonatype/Snyk/GitHub legitimately returned nothing because they simply had not
    published inside the window. Five sources, five different meanings for "no items today"
    — which is the argument for the per-source health table existing at all.

24. **A test with a hard-coded date is a bomb with a timer on it.** `test_run_pipeline` fed the
    orchestrator an RSS item dated `03 Aug 2026`. The pipeline drops anything published before
    `now - FETCH_WINDOW_DAYS`, so the fixture passed the day it was written and silently began
    failing three days later — nothing to do with the code, and it would have greeted anyone
    cloning the repo with a red suite. Any fixture compared against `now` has to be *relative*
    to now. Found only by re-running the suite days after the work was "finished", which is an
    argument for verifying on a schedule rather than once at the end.
