# Ribbit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Ribbit — a GenAI-enriched daily competitive-intelligence pipeline + React dashboard for JFrog's CI team, runnable by reviewers with `docker compose up` and zero API keys.

**Architecture:** FastAPI backend runs a daily pipeline (fetch → dedupe → enrich → delta → digest → battlecards) over YAML-configured sources, storing to SQLite (+FTS5). All LLM calls go through a provider-agnostic LiteLLM gateway with schema-validated structured outputs and enforced citations. React+TS SPA (5 tabs) consumes the REST API. Keyless runs auto-load a bundled demo dataset.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, SQLite FTS5, LiteLLM, feedparser, httpx, APScheduler, pytest · React 18, TypeScript, Vite, Tailwind v4, TanStack Query, react-router, recharts, vitest · Docker Compose, nginx, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-03-competitive-intel-tool-design.md` · **ADRs:** `DECISIONS.md`

**Conventions for every task:**
- Work from repo root `ribbit/`. Backend commands run in `backend/` with the venv active: `cd backend && source .venv/bin/activate`.
- Commit after every green test run. Update `DECISIONS.md` / `INSIGHTS.md` immediately when you deviate or learn something (standing user requirement).
- All external HTTP in tests is faked (httpx.MockTransport / monkeypatch). Tests never hit the network or a real LLM.

---

### Task 1: Backend scaffold & settings

**Files:**
- Create: `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/app/__init__.py`, `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Create environment and dependency files**

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
pydantic>=2.7
pydantic-settings>=2.2
litellm>=1.48
feedparser>=6.0
httpx>=0.27
apscheduler>=3.10
pyyaml>=6.0
```

`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.23
ruff>=0.5
```

`backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

Run:
```bash
cd backend && python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
```
Expected: installs succeed (litellm is the slowest, ~1 min).

- [ ] **Step 2: Write the failing test**

`backend/tests/test_config.py`:
```python
from pathlib import Path

from app.config import Settings


def test_defaults_load_without_env():
    s = Settings(_env_file=None)
    assert s.llm_provider == "anthropic"
    assert s.demo_mode == "auto"
    assert s.refresh_hour == 7
    assert s.database_url.startswith("sqlite:///")
    assert s.config_dir.name == "config"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("REFRESH_HOUR", "5")
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    assert s.refresh_hour == 5


def test_config_dir_exists():
    s = Settings(_env_file=None)
    assert isinstance(s.config_dir, Path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'` (or ImportError for Settings).

- [ ] **Step 4: Implement settings**

`backend/app/__init__.py`: empty file.

`backend/app/config.py`:
```python
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"  # anthropic | openai | gemini | ollama
    llm_model: str = "claude-haiku-4-5"
    ollama_model: str = "llama3.1:8b"
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
    llm_fallback_provider: str = ""  # empty = no fallback
    tavily_api_key: SecretStr = SecretStr("")
    refresh_hour: int = 7
    demo_mode: str = "auto"  # auto | on | off
    enable_scheduler: bool = True
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'ribbit.db'}"
    config_dir: Path = REPO_ROOT / "config"
    demo_seed_path: Path = REPO_ROOT / "data" / "demo" / "seed.json"
    fetch_window_days: int = 2
```

Note: `REPO_ROOT` is `ribbit/` (config.py is at `backend/app/config.py`, two parents up).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(backend): scaffold with pydantic settings"
```

---

### Task 2: Domain config YAMLs + loader

**Files:**
- Create: `config/competitors.yaml`, `config/industry_feeds.yaml`, `config/jfrog_capabilities.yaml`, `config/feature_matrix.yaml`, `backend/app/config_data.py`
- Test: `backend/tests/test_config_data.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_config_data.py`:
```python
from app.config import Settings
from app.config_data import AppConfig


def cfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_competitors_load_core5():
    c = cfg()
    slugs = [comp["slug"] for comp in c.competitors]
    assert slugs == ["sonatype", "gitlab", "github", "docker", "snyk"]
    for comp in c.competitors:
        assert comp["name"] and comp["color"]
        assert isinstance(comp["sources"].get("rss", []), list)
        base = comp["battlecard_base"]
        assert base["strengths"] and base["weaknesses"] and base["how_jfrog_wins"]


def test_industry_feeds_load():
    c = cfg()
    assert len(c.industry_feeds) >= 3
    assert all(f["url"].startswith("http") for f in c.industry_feeds)


def test_capabilities_and_matrix():
    c = cfg()
    assert len(c.jfrog_capabilities) >= 8
    assert c.matrix["vendors"][0] == "jfrog"
    caps = {r["capability"] for r in c.matrix["rows"]}
    assert len(caps) == len(c.matrix["rows"])  # no duplicate rows
    for row in c.matrix["rows"]:
        assert set(row["values"]) == set(c.matrix["vendors"])


def test_slug_helpers():
    c = cfg()
    assert c.competitor_by_slug("snyk")["name"] == "Snyk"
    assert c.slugs() == ["sonatype", "gitlab", "github", "docker", "snyk"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config_data'`.

- [ ] **Step 3: Create the four YAML files**

`config/competitors.yaml` (complete file — feed URLs are best-known-good; the source-health panel surfaces any that die, and Task 24 verifies them live):
```yaml
competitors:
  - slug: sonatype
    name: Sonatype
    color: "#79b62f"
    sources:
      rss:
        - "https://www.sonatype.com/blog/rss.xml"
      hn_query: 'sonatype OR "nexus repository"'
      reddit:
        subreddits: [devops]
        query: "sonatype OR nexus"
      tavily_query: "Sonatype Nexus news"
    battlecard_base:
      strengths:
        - "Deep roots in the Java/Maven ecosystem (stewards of Maven Central)"
        - "Strong open-source intelligence data (OSS Index) feeding policy enforcement"
      weaknesses:
        - "Narrower package-format coverage than Artifactory's universal approach"
        - "Fragmented product line (Repository vs Lifecycle vs Firewall) complicates adoption"
      how_jfrog_wins:
        - "Universal 30+ package types in one platform vs Java-centric heritage"
        - "Xray contextual analysis reduces false-positive noise vs raw policy alerts"
  - slug: gitlab
    name: GitLab
    color: "#fc6d26"
    sources:
      rss:
        - "https://about.gitlab.com/atom.xml"
      hn_query: "gitlab"
      reddit:
        subreddits: [devops, gitlab]
        query: "gitlab package OR registry OR security"
      tavily_query: "GitLab DevSecOps release news"
    battlecard_base:
      strengths:
        - "Single-application DevSecOps story: repo, CI, registry, scanning in one UI"
        - "Strong momentum with platform-engineering buyers"
      weaknesses:
        - "Package/container registry is a checkbox feature - shallow vs dedicated artifact platforms"
        - "Security scanning depth trails specialist tools"
      how_jfrog_wins:
        - "Artifactory is CI-agnostic: works with GitLab CI, Jenkins, GitHub Actions alike"
        - "Enterprise binary management (replication, edge nodes) GitLab lacks"
  - slug: github
    name: GitHub
    color: "#8b5cf6"
    sources:
      rss:
        - "https://github.blog/feed/"
        - "https://github.blog/changelog/feed/"
      hn_query: '"github packages" OR "github advanced security" OR dependabot'
      reddit:
        subreddits: [devops]
        query: "github packages OR dependabot"
      tavily_query: "GitHub Packages Advanced Security news"
    battlecard_base:
      strengths:
        - "Default home of developers; Packages and Actions are zero-friction add-ons"
        - "Microsoft backing and Copilot-led AI momentum"
      weaknesses:
        - "GitHub Packages has limited format support and weak enterprise artifact governance"
        - "Advanced Security is repo-centric, not artifact/binary-centric"
      how_jfrog_wins:
        - "Binary-focused lifecycle (promotion, distribution, air-gapped) beyond source hosting"
        - "Multi-cloud/hybrid neutrality vs Azure gravity"
  - slug: docker
    name: Docker
    color: "#2496ed"
    sources:
      rss:
        - "https://www.docker.com/blog/feed/"
      hn_query: '"docker hub" OR "docker scout"'
      reddit:
        subreddits: [docker, devops]
        query: "docker hub OR docker scout"
      tavily_query: "Docker Hub Docker Scout news"
    battlecard_base:
      strengths:
        - "Docker Hub is the world's default public container registry"
        - "Massive developer mindshare and CLI ubiquity"
      weaknesses:
        - "Registry is container-only; no universal artifact story"
        - "Monetization pivots (rate limits, licensing) created enterprise distrust"
      how_jfrog_wins:
        - "Artifactory serves containers AND every other package type with one permission model"
        - "Enterprise-grade private registry with replication vs public-registry heritage"
  - slug: snyk
    name: Snyk
    color: "#4c4a73"
    sources:
      rss:
        - "https://snyk.io/blog/feed/"
      hn_query: "snyk"
      reddit:
        subreddits: [devops, netsec]
        query: "snyk"
      tavily_query: "Snyk developer security news"
    battlecard_base:
      strengths:
        - "Developer-first UX for SCA/SAST with strong IDE and PR integration"
        - "Large vulnerability database with security research brand"
      weaknesses:
        - "Scanning-only: no artifact storage, promotion, or distribution"
        - "Pricing scales steeply with developer count"
      how_jfrog_wins:
        - "Xray scans where binaries actually live (the registry), enabling block-at-download"
        - "Contextual analysis (is the vulnerable function actually reachable?) cuts alert fatigue"
```

`config/industry_feeds.yaml`:
```yaml
feeds:
  - name: CNCF Blog
    url: "https://www.cncf.io/feed/"
  - name: The New Stack
    url: "https://thenewstack.io/feed/"
  - name: InfoQ DevOps
    url: "https://feed.infoq.com/devops/"
  - name: DevOps.com
    url: "https://devops.com/feed/"
```

`config/jfrog_capabilities.yaml` (grounds Delta analysis — the LLM may only cite these):
```yaml
capabilities:
  - name: Artifactory universal repository
    notes: "30+ package types (Maven, npm, PyPI, Docker/OCI, Go, NuGet, Helm, Conan...) with one metadata/permission model; local, remote-proxy and virtual repos."
  - name: Xray SCA scanning
    notes: "Scans artifacts/dependencies in the registry for CVEs, licenses, operational risk; deep recursive scanning inside archives and images."
  - name: Xray contextual analysis
    notes: "Determines whether a CVE is actually applicable/exploitable in the specific artifact context (is the vulnerable code reachable/configured), reducing false positives."
  - name: JFrog Advanced Security
    notes: "Secrets detection, IaC scanning, exposed-services analysis, malicious-package detection."
  - name: JFrog Curation
    notes: "Blocks risky open-source packages at the door (before they enter the org) based on policy."
  - name: SBOM generation & export
    notes: "SBOM (CycloneDX/SPDX) for builds and releases; build-info provenance metadata."
  - name: Distribution & edge nodes
    notes: "Signed release bundles distributed to edges/air-gapped environments."
  - name: Replication & multi-site
    notes: "Push/pull replication across regions and hybrid/multi-cloud topologies."
  - name: CI/CD integration & Build Info
    notes: "JFrog CLI + native plugins (GitHub Actions, Jenkins, Azure DevOps) publish traceable build metadata."
  - name: JFrog ML (MLOps)
    notes: "Model registry/management extending artifact governance to ML models."
```

`config/feature_matrix.yaml` (curated comparison — user reviews facts before the demo; levels: full | partial | addon | none):
```yaml
vendors: [jfrog, sonatype, gitlab, github, docker, snyk]
vendor_labels:
  jfrog: JFrog
  sonatype: Sonatype
  gitlab: GitLab
  github: GitHub
  docker: Docker
  snyk: Snyk
rows:
  - capability: Universal artifact management
    values:
      jfrog: {level: full, note: "30+ package types"}
      sonatype: {level: full, note: "Strong Java heritage"}
      gitlab: {level: partial, note: "Basic registry per project"}
      github: {level: partial, note: "Limited formats"}
      docker: {level: none, note: "Containers only"}
      snyk: {level: none, note: "No storage"}
  - capability: Container registry
    values:
      jfrog: {level: full, note: ""}
      sonatype: {level: full, note: ""}
      gitlab: {level: full, note: ""}
      github: {level: full, note: "ghcr.io"}
      docker: {level: full, note: "The default public hub"}
      snyk: {level: none, note: ""}
  - capability: SCA / vulnerability scanning
    values:
      jfrog: {level: full, note: "Xray"}
      sonatype: {level: full, note: "Lifecycle/Firewall"}
      gitlab: {level: partial, note: "Ultimate tier"}
      github: {level: partial, note: "Dependabot/GHAS"}
      docker: {level: partial, note: "Docker Scout"}
      snyk: {level: full, note: "Core product"}
  - capability: Contextual / reachability analysis
    values:
      jfrog: {level: full, note: "Applicability scanning"}
      sonatype: {level: partial, note: ""}
      gitlab: {level: none, note: ""}
      github: {level: none, note: ""}
      docker: {level: none, note: ""}
      snyk: {level: partial, note: "Reachability beta"}
  - capability: SBOM generation
    values:
      jfrog: {level: full, note: ""}
      sonatype: {level: full, note: ""}
      gitlab: {level: partial, note: ""}
      github: {level: partial, note: ""}
      docker: {level: partial, note: ""}
      snyk: {level: partial, note: ""}
  - capability: Release distribution / air-gap
    values:
      jfrog: {level: full, note: "Distribution + edges"}
      sonatype: {level: partial, note: ""}
      gitlab: {level: none, note: ""}
      github: {level: none, note: ""}
      docker: {level: none, note: ""}
      snyk: {level: none, note: ""}
  - capability: CI/CD pipelines
    values:
      jfrog: {level: partial, note: "Integrations-first"}
      sonatype: {level: none, note: ""}
      gitlab: {level: full, note: "Core strength"}
      github: {level: full, note: "Actions"}
      docker: {level: none, note: ""}
      snyk: {level: none, note: ""}
  - capability: ML model management
    values:
      jfrog: {level: full, note: "JFrog ML"}
      sonatype: {level: none, note: ""}
      gitlab: {level: partial, note: ""}
      github: {level: partial, note: "Models on Hub"}
      docker: {level: partial, note: "AI catalog"}
      snyk: {level: none, note: ""}
```

- [ ] **Step 4: Implement the loader**

`backend/app/config_data.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


@dataclass
class AppConfig:
    competitors: list[dict]
    industry_feeds: list[dict]
    jfrog_capabilities: list[dict]
    matrix: dict

    @classmethod
    def load(cls, config_dir: Path) -> "AppConfig":
        return cls(
            competitors=_load(config_dir / "competitors.yaml")["competitors"],
            industry_feeds=_load(config_dir / "industry_feeds.yaml")["feeds"],
            jfrog_capabilities=_load(config_dir / "jfrog_capabilities.yaml")["capabilities"],
            matrix=_load(config_dir / "feature_matrix.yaml"),
        )

    def slugs(self) -> list[str]:
        return [c["slug"] for c in self.competitors]

    def competitor_by_slug(self, slug: str) -> dict | None:
        return next((c for c in self.competitors if c["slug"] == slug), None)

    def capabilities_text(self) -> str:
        return "\n".join(f"- {c['name']}: {c['notes']}" for c in self.jfrog_capabilities)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config_data.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add config backend && git commit -m "feat(config): competitor/industry/capability/matrix YAML + loader"
```

---

### Task 3: Database models + FTS5 + shared test fixtures

**Files:**
- Create: `backend/app/models.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:
```python
from sqlalchemy import text

from app.models import Article, Digest


def test_tables_created(session):
    session.add(Article(url="https://x.com/a", content_hash="h1", title="Hello Nexus",
                        source_name="t", source_type="rss"))
    session.commit()
    assert session.query(Article).count() == 1


def test_fts_syncs_on_insert_update(session):
    a = Article(url="https://x.com/b", content_hash="h2", title="GitLab ships scanner",
                source_name="t", source_type="rss")
    session.add(a)
    session.commit()
    hits = session.execute(text(
        "SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'gitlab'")).fetchall()
    assert hits and hits[0][0] == a.id

    a.summary = "A brand new SAST engine"
    session.commit()
    hits = session.execute(text(
        "SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'sast'")).fetchall()
    assert hits and hits[0][0] == a.id


def test_digest_unique_date(session):
    session.add(Digest(date="2026-08-03", exec_summary="s", sections={}, model_used="m"))
    session.commit()
    assert session.query(Digest).filter_by(date="2026-08-03").one().exec_summary == "s"
```

- [ ] **Step 2: Create conftest with shared fixtures**

`backend/tests/conftest.py`:
```python
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Article, init_db


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def session(session_factory):
    with session_factory() as s:
        yield s


def make_article(session: Session, *, url: str, title: str, status: str = "new", **kw) -> Article:
    a = Article(url=url, content_hash=f"hash-{url}", title=title,
                source_name=kw.pop("source_name", "Test Feed"),
                source_type=kw.pop("source_type", "rss"),
                published_at=kw.pop("published_at", datetime(2026, 8, 3, 9, tzinfo=timezone.utc)),
                status=status, **kw)
    session.add(a)
    session.commit()
    return a
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 4: Implement models**

`backend/app/models.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str]
    body_excerpt: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str]
    source_type: Mapped[str]  # rss | hackernews | reddit | tavily | demo
    published_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[str] = mapped_column(default="new", index=True)  # new|enriched|irrelevant|failed
    # enrichment
    relevant: Mapped[bool | None]
    competitors: Mapped[list | None] = mapped_column(JSON)
    domain: Mapped[str | None]
    event_type: Mapped[str | None]
    summary: Mapped[str | None] = mapped_column(Text)
    jfrog_impact: Mapped[int | None]
    so_what: Mapped[str | None] = mapped_column(Text)
    enriched_at: Mapped[datetime | None]
    # delta (only when jfrog_impact >= 4)
    delta_move: Mapped[str | None] = mapped_column(Text)
    delta_jfrog_equivalent: Mapped[str | None] = mapped_column(Text)
    delta_strategic_impact: Mapped[str | None]  # high|medium|low
    delta_talking_points: Mapped[list | None] = mapped_column(JSON)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(unique=True, index=True)  # YYYY-MM-DD
    exec_summary: Mapped[str] = mapped_column(Text)
    sections: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)
    model_used: Mapped[str] = mapped_column(default="")


class Battlecard(Base):
    __tablename__ = "battlecards"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_slug: Mapped[str] = mapped_column(unique=True, index=True)
    recent_moves: Mapped[list] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(index=True)
    source_name: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ok: Mapped[bool] = mapped_column(default=True)
    items_found: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)


FTS_STATEMENTS = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        title, body_excerpt, summary, content='articles', content_rowid='id')""",
    """CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts(rowid, title, body_excerpt, summary)
        VALUES (new.id, new.title, coalesce(new.body_excerpt,''), coalesce(new.summary,''));
    END""",
    """CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, body_excerpt, summary)
        VALUES('delete', old.id, old.title, coalesce(old.body_excerpt,''), coalesce(old.summary,''));
        INSERT INTO articles_fts(rowid, title, body_excerpt, summary)
        VALUES (new.id, new.title, coalesce(new.body_excerpt,''), coalesce(new.summary,''));
    END""",
    """CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
        INSERT INTO articles_fts(articles_fts, rowid, title, body_excerpt, summary)
        VALUES('delete', old.id, old.title, coalesce(old.body_excerpt,''), coalesce(old.summary,''));
    END""",
]


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in FTS_STATEMENTS:
            conn.exec_driver_sql(stmt)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(db): SQLAlchemy models with FTS5 index and sync triggers"
```

---

### Task 4: URL canonicalization, hashing, dedupe insert

**Files:**
- Create: `backend/app/pipeline/__init__.py`, `backend/app/pipeline/dedupe.py`
- Test: `backend/tests/test_dedupe.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_dedupe.py`:
```python
from datetime import datetime, timezone

from app.pipeline.dedupe import canonical_url, content_hash, insert_new_items
from app.sources.base import RawItem


def item(url: str, title: str = "Snyk raises prices") -> RawItem:
    return RawItem(title=title, url=url, body_excerpt="body", source_name="Feed",
                   source_type="rss", published_at=datetime(2026, 8, 3, tzinfo=timezone.utc))


def test_canonical_url_strips_tracking_and_normalizes():
    u = "HTTPS://Snyk.io/Blog/Post/?utm_source=x&utm_medium=y&fbclid=z&keep=1#frag"
    assert canonical_url(u) == "https://snyk.io/Blog/Post?keep=1"


def test_content_hash_stable_and_case_insensitive():
    assert content_hash("Title A", "body") == content_hash("  title a ", "body")
    assert content_hash("Title A", "body") != content_hash("Title B", "body")


def test_insert_new_items_dedupes(session):
    items = [
        item("https://snyk.io/blog/p1?utm_source=rss"),
        item("https://snyk.io/blog/p1"),                      # same after canonicalization
        item("https://other.com/mirror", title="Snyk raises prices"),  # same content hash? no - hash includes excerpt+title only
    ]
    inserted = insert_new_items(session, items)
    # p1 dedupes to one; mirror has identical title+excerpt -> identical hash -> also deduped
    assert inserted == 1
    inserted_again = insert_new_items(session, items)
    assert inserted_again == 0
```

Note the intent: dedupe fires on canonical URL **or** identical content hash (title+excerpt), catching syndicated copies.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedupe.py -v`
Expected: FAIL — `ModuleNotFoundError` (app.pipeline.dedupe / app.sources.base don't exist yet).

- [ ] **Step 3: Create RawItem (minimal sources/base.py now; adapters come in Task 7)**

`backend/app/sources/__init__.py`: empty file.

`backend/app/sources/base.py`:
```python
from datetime import datetime

from pydantic import BaseModel

USER_AGENT = {"User-Agent": "RibbitCI/0.1 (competitive-intel demo; contact: repo README)"}


class RawItem(BaseModel):
    title: str
    url: str
    body_excerpt: str = ""
    source_name: str
    source_type: str  # rss | hackernews | reddit | tavily
    published_at: datetime | None = None
```

- [ ] **Step 4: Implement dedupe**

`backend/app/pipeline/__init__.py`: empty file.

`backend/app/pipeline/dedupe.py`:
```python
import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article
from app.sources.base import RawItem

_DROP_PARAMS = {"fbclid", "gclid", "ref", "mc_cid", "mc_eid", "source"}


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in _DROP_PARAMS]
    path = p.path.rstrip("/") if p.path not in ("", "/") else "/"
    return urlunsplit((p.scheme.lower() or "https", p.netloc.lower(), path,
                       urlencode(query), ""))


def content_hash(title: str, excerpt: str) -> str:
    basis = f"{title.strip().lower()}|{excerpt.strip().lower()[:500]}"
    return hashlib.sha256(basis.encode()).hexdigest()


def insert_new_items(session: Session, items: list[RawItem]) -> int:
    inserted = 0
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    for it in items:
        if not it.url or not it.title:
            continue
        url = canonical_url(it.url)
        h = content_hash(it.title, it.body_excerpt)
        if url in seen_urls or h in seen_hashes:
            continue
        exists = session.scalar(select(Article.id).where(
            (Article.url == url) | (Article.content_hash == h)))
        if exists:
            continue
        session.add(Article(url=url, content_hash=h, title=it.title.strip(),
                            body_excerpt=it.body_excerpt, source_name=it.source_name,
                            source_type=it.source_type, published_at=it.published_at))
        seen_urls.add(url)
        seen_hashes.add(h)
        inserted += 1
    session.commit()
    return inserted
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dedupe.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(pipeline): canonical URL + content-hash dedupe insert"
```

---

### Task 5: Structured-output schemas + citation enforcement

**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_schemas.py`:
```python
import pytest
from pydantic import ValidationError

from app.llm.schemas import (Claim, DigestSchema, Enrichment, enforce_battlecard_citations,
                             enforce_digest_citations)


def test_enrichment_validates_bounds():
    e = Enrichment(relevant=True, competitors=["snyk"], domain="devsecops_scanning",
                   event_type="pricing_change", summary="s", jfrog_impact=4, so_what="w")
    assert e.jfrog_impact == 4
    with pytest.raises(ValidationError):
        Enrichment(relevant=True, domain="devsecops_scanning", event_type="other",
                   summary="s", jfrog_impact=9, so_what="w")
    with pytest.raises(ValidationError):
        Enrichment(relevant=True, domain="not_a_domain", event_type="other",
                   summary="s", jfrog_impact=3, so_what="w")


def _digest() -> DigestSchema:
    return DigestSchema(
        exec_summary="day summary",
        top_developments=[Claim(text="valid claim", article_ids=[1, 99]),
                          Claim(text="orphan claim", article_ids=[99])],
        by_competitor=[{"competitor": "snyk",
                        "highlights": [{"text": "h", "article_ids": [2]}]}],
        threats_opportunities=[{"kind": "threat", "text": "t", "article_ids": [1]},
                               {"kind": "opportunity", "text": "o", "article_ids": []}],
    )


def test_enforce_digest_citations_drops_invalid():
    cleaned = enforce_digest_citations(_digest(), valid_ids={1, 2})
    assert [c.text for c in cleaned.top_developments] == ["valid claim"]
    assert cleaned.top_developments[0].article_ids == [1]          # 99 stripped
    assert cleaned.by_competitor[0].highlights[0].article_ids == [2]
    kinds = [t.kind for t in cleaned.threats_opportunities]
    assert kinds == ["threat"]                                     # uncited opportunity dropped


def test_enforce_battlecard_citations():
    moves = [Claim(text="cited", article_ids=[5]), Claim(text="uncited", article_ids=[42])]
    assert [m.text for m in enforce_battlecard_citations(moves, {5})] == ["cited"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm'`.

- [ ] **Step 3: Implement schemas**

`backend/app/llm/__init__.py`: empty file.

`backend/app/llm/schemas.py`:
```python
from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["artifact_management", "container_registry", "devsecops_scanning",
                 "cicd", "sbom_supply_chain", "other"]
EventType = Literal["product_launch", "feature_update", "security_advisory",
                    "pricing_change", "funding_ma", "partnership", "other"]


class Enrichment(BaseModel):
    relevant: bool
    competitors: list[str] = Field(default_factory=list)
    domain: Domain = "other"
    event_type: EventType = "other"
    summary: str = ""
    jfrog_impact: int = Field(1, ge=1, le=5)
    so_what: str = ""


class Delta(BaseModel):
    competitor_move: str
    jfrog_equivalent: str
    strategic_impact: Literal["high", "medium", "low"]
    talking_points: list[str] = Field(default_factory=list, max_length=3)


class Claim(BaseModel):
    text: str
    article_ids: list[int] = Field(default_factory=list)


class CompetitorSection(BaseModel):
    competitor: str
    highlights: list[Claim] = Field(default_factory=list)


class TypedClaim(Claim):
    kind: Literal["threat", "opportunity"]


class DigestSchema(BaseModel):
    exec_summary: str
    top_developments: list[Claim] = Field(default_factory=list)
    by_competitor: list[CompetitorSection] = Field(default_factory=list)
    threats_opportunities: list[TypedClaim] = Field(default_factory=list)


class BattlecardGen(BaseModel):
    recent_moves: list[Claim] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    answer: str
    citation_ids: list[int] = Field(default_factory=list)


def _clean_claims(claims: list, valid_ids: set[int]) -> list:
    """Strip unknown article_ids; drop claims left with none. The hallucination firewall."""
    cleaned = []
    for c in claims:
        ids = [i for i in c.article_ids if i in valid_ids]
        if ids:
            cleaned.append(c.model_copy(update={"article_ids": ids}))
    return cleaned


def enforce_digest_citations(d: DigestSchema, valid_ids: set[int]) -> DigestSchema:
    return d.model_copy(update={
        "top_developments": _clean_claims(d.top_developments, valid_ids),
        "by_competitor": [s.model_copy(update={"highlights": _clean_claims(s.highlights, valid_ids)})
                          for s in d.by_competitor
                          if _clean_claims(s.highlights, valid_ids)],
        "threats_opportunities": _clean_claims(d.threats_opportunities, valid_ids),
    })


def enforce_battlecard_citations(moves: list[Claim], valid_ids: set[int]) -> list[Claim]:
    return _clean_claims(moves, valid_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(llm): structured-output schemas with citation enforcement"
```

---

### Task 6: LLM gateway (LiteLLM) + prompts

**Files:**
- Create: `backend/app/llm/gateway.py`, `backend/app/llm/prompts.py`
- Test: `backend/tests/test_gateway.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_gateway.py`:
```python
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm.gateway import LLMGateway, _extract_json
from app.llm.schemas import Enrichment

GOOD = ('{"relevant": true, "competitors": ["snyk"], "domain": "devsecops_scanning",'
        ' "event_type": "pricing_change", "summary": "s", "jfrog_impact": 4, "so_what": "w"}')


def fake_completion(replies: list[str], calls: list[dict]):
    def _fake(**kwargs):
        calls.append(kwargs)
        text = replies.pop(0)
        if text == "RAISE":
            raise RuntimeError("provider down")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    return _fake


def settings(**kw) -> Settings:
    return Settings(_env_file=None, anthropic_api_key="k", **kw)


def test_extract_json_strips_fences_and_prose():
    assert _extract_json("Sure!\n```json\n{\"a\": 1}\n```\nDone.") == '{"a": 1}'
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_complete_json_happy_path(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion", fake_completion([GOOD], calls))
    gw = LLMGateway(settings())
    out = gw.complete_json("sys", "user", Enrichment)
    assert out and out.jfrog_impact == 4
    assert calls[0]["model"] == "anthropic/claude-haiku-4-5"


def test_repair_retry_on_invalid_json(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["not json at all", GOOD], calls))
    gw = LLMGateway(settings())
    out = gw.complete_json("sys", "user", Enrichment)
    assert out and out.relevant is True
    assert len(calls) == 2 and "previous output was invalid" in calls[1]["messages"][-1]["content"]


def test_fallback_provider_on_error(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["RAISE", GOOD], calls))
    gw = LLMGateway(settings(llm_fallback_provider="ollama"))
    out = gw.complete_json("sys", "user", Enrichment)
    assert out is not None
    assert calls[1]["model"] == "ollama/llama3.1:8b"


def test_gives_up_returns_none(monkeypatch):
    monkeypatch.setattr("app.llm.gateway.litellm.completion",
                        fake_completion(["nope", "still nope"], []))
    gw = LLMGateway(settings())
    assert gw.complete_json("sys", "user", Enrichment) is None


def test_available_by_key():
    assert LLMGateway(settings()).available() is True
    s = Settings(_env_file=None)  # no keys
    assert LLMGateway(s)._has_key("anthropic") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gateway.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm.gateway'`.

- [ ] **Step 3: Implement gateway**

`backend/app/llm/gateway.py`:
```python
from __future__ import annotations

import json
import logging
from typing import TypeVar

import httpx
import litellm
from pydantic import BaseModel, ValidationError

from app.config import Settings

log = logging.getLogger("ribbit.llm")
litellm.suppress_debug_info = True

T = TypeVar("T", bound=BaseModel)

REPAIR_SUFFIX = ("\n\nYour previous output was invalid for the schema. "
                 "Return ONLY the corrected raw JSON object, no prose, no code fences.")


def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip().removeprefix("json").strip()
            if p.startswith("{"):
                text = p
                break
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


class LLMGateway:
    def __init__(self, settings: Settings):
        self.s = settings

    def _key_for(self, provider: str) -> str:
        secret = {"anthropic": self.s.anthropic_api_key,
                  "openai": self.s.openai_api_key,
                  "gemini": self.s.gemini_api_key}.get(provider)
        return secret.get_secret_value() if secret else ""

    def _has_key(self, provider: str) -> bool:
        return bool(self._key_for(provider))

    def _ollama_up(self) -> bool:
        try:
            return httpx.get(f"{self.s.ollama_base_url}/api/tags", timeout=1.5).status_code == 200
        except Exception:
            return False

    def _provider_usable(self, provider: str) -> bool:
        return self._ollama_up() if provider == "ollama" else self._has_key(provider)

    def available(self) -> bool:
        return any(self._provider_usable(p) for p in self._providers())

    def _providers(self) -> list[str]:
        chain = [self.s.llm_provider]
        if self.s.llm_fallback_provider and self.s.llm_fallback_provider != self.s.llm_provider:
            chain.append(self.s.llm_fallback_provider)
        return chain

    def _model_and_kwargs(self, provider: str) -> tuple[str, dict]:
        if provider == "ollama":
            return f"ollama/{self.s.ollama_model}", {"api_base": self.s.ollama_base_url}
        if provider == "gemini":
            return f"gemini/{self.s.llm_model}", {"api_key": self._key_for("gemini")}
        return f"{provider}/{self.s.llm_model}", {"api_key": self._key_for(provider)}

    def complete_json(self, system: str, user: str, schema: type[T],
                      temperature: float = 0.2) -> T | None:
        schema_hint = json.dumps(schema.model_json_schema())
        sys_msg = f"{system}\n\nRespond with ONLY a raw JSON object matching this JSON Schema:\n{schema_hint}"
        for provider in self._providers():
            user_msg = user
            for attempt in (1, 2):
                try:
                    model, extra = self._model_and_kwargs(provider)
                    resp = litellm.completion(
                        model=model, temperature=temperature, timeout=90,
                        messages=[{"role": "system", "content": sys_msg},
                                  {"role": "user", "content": user_msg}],
                        **extra)
                    text = resp.choices[0].message.content or ""
                    return schema.model_validate_json(_extract_json(text))
                except (ValidationError, json.JSONDecodeError) as e:
                    log.warning("invalid JSON from %s (attempt %s): %s", provider, attempt, e)
                    user_msg = user + REPAIR_SUFFIX
                except Exception as e:  # provider/network error -> try next provider
                    log.warning("provider %s failed: %s", provider, e)
                    break
        return None
```

- [ ] **Step 4: Write the prompts module (static strings, no test — exercised via stage tests)**

`backend/app/llm/prompts.py`:
```python
ENRICH_SYSTEM = """You are a competitive-intelligence analyst for JFrog (Artifactory: universal \
artifact management; Xray: security scanning of artifacts). You classify ONE news item.

Tracked competitors (use these exact slugs): {slugs}

domain (pick ONE): artifact_management | container_registry | devsecops_scanning | cicd | sbom_supply_chain | other
event_type (pick ONE): product_launch | feature_update | security_advisory | pricing_change | funding_ma | partnership | other

Rules:
- relevant=true ONLY if the item concerns a tracked competitor OR the software-supply-chain / \
artifact-management / DevSecOps domain. Generic tech/AI/corporate news is relevant=false.
- competitors: slugs of tracked competitors actually involved (empty list if none).
- summary: max 2 factual sentences, no hype.
- jfrog_impact: 1=noise, 2=monitor, 3=notable, 4=significant threat/opportunity, 5=urgent strategic move.
- so_what: one sentence on what it means for JFrog specifically.

Example A (relevant): "Snyk announces 30% price increase for Enterprise tier" ->
{{"relevant": true, "competitors": ["snyk"], "domain": "devsecops_scanning", "event_type": "pricing_change",
"summary": "Snyk raised Enterprise tier pricing by 30%.", "jfrog_impact": 4,
"so_what": "Displacement window: Xray bundling undercuts Snyk renewals."}}

Example B (noise): "Microsoft launches new Teams AI features" ->
{{"relevant": false, "competitors": [], "domain": "other", "event_type": "other",
"summary": "", "jfrog_impact": 1, "so_what": ""}}"""

ENRICH_USER = """Title: {title}
Source: {source_name} ({source_type})
Published: {published_at}
Excerpt: {excerpt}"""

DELTA_SYSTEM = """You are JFrog's competitive strategist. A high-impact competitor move was detected.
Produce a delta analysis. CRITICAL GROUNDING RULE: in jfrog_equivalent you may ONLY reference JFrog
capabilities from the official capability sheet below. If nothing matches, say "No direct JFrog
equivalent today" and explain the gap. Never invent JFrog features.

JFrog capability sheet:
{capabilities}

Fields:
- competitor_move: one sentence, factual.
- jfrog_equivalent: how JFrog's existing capabilities compare (sheet-grounded).
- strategic_impact: high | medium | low (threat or opportunity magnitude for JFrog).
- talking_points: up to 3 short bullets sales/product can use."""

DELTA_USER = """Competitor(s): {competitors}
Move ({event_type}, domain {domain}): {title}
Summary: {summary}"""

DIGEST_SYSTEM = """You are writing the daily competitive-intelligence digest for JFrog's CI team.
You get today's enriched news items, each with an integer id. Cite by id.

CITATION RULE: every claim object MUST include article_ids drawn ONLY from the provided ids.
Claims without a valid id will be deleted by the system. Do not use outside knowledge.

Fields:
- exec_summary: 2-4 sentences, the day in brief for an executive. This field carries no
  article_ids and is therefore NOT citation-checked by the system, so it is held to a stricter
  rule instead: it may ONLY synthesize and prioritize what you state in the cited sections
  below. It must introduce no company, product, number, date, or event that does not appear in
  a cited claim. If the cited sections are empty, say the day was quiet — do not fill space.
- top_developments: 3-6 most important items (text + article_ids).
- by_competitor: per competitor with news today: 1-3 highlight claims each.
- threats_opportunities: kind=threat or opportunity, the strategic reads of the day."""

DIGEST_USER = """Date: {date}
Items:
{items}"""

BATTLECARD_SYSTEM = """You maintain the "{name}" battlecard for JFrog's CI team. From the recent
enriched items below, write recent_moves: 2-6 claims about what this competitor has been doing lately.
CITATION RULE: each claim MUST carry article_ids drawn ONLY from provided ids; uncited claims are
deleted. Factual tone, no speculation beyond the items."""

BATTLECARD_USER = """Competitor: {name}
Recent items:
{items}"""

CHAT_SYSTEM = """You are Ribbit, JFrog's competitive-intelligence analyst. Answer ONLY from the
retrieved articles below. If they don't contain the answer, say so plainly. Cite article ids you
used in citation_ids. Keep answers under 150 words.

Retrieved articles:
{articles}"""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_gateway.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(llm): provider-agnostic LiteLLM gateway with repair retry + prompts"
```

---

### Task 7: Source adapters (RSS, Hacker News, Reddit, Tavily)

**Files:**
- Create: `backend/app/sources/rss.py`, `backend/app/sources/hackernews.py`, `backend/app/sources/reddit.py`, `backend/app/sources/tavily.py`
- Create fixtures: `backend/tests/fixtures/rss_sample.xml`, `backend/tests/fixtures/hn_sample.json`, `backend/tests/fixtures/reddit_sample.json`
- Test: `backend/tests/test_adapters.py`

- [ ] **Step 1: Create fixtures**

`backend/tests/fixtures/rss_sample.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Vendor Blog</title>
<item>
  <title>Nexus Repository 3.99 adds SBOM export</title>
  <link>https://vendor.example/blog/nexus-399?utm_source=rss</link>
  <description><![CDATA[<p>Sonatype today announced <b>SBOM export</b> for all formats.</p>]]></description>
  <pubDate>Mon, 03 Aug 2026 08:00:00 GMT</pubDate>
</item>
<item>
  <title>Old post outside window</title>
  <link>https://vendor.example/blog/old</link>
  <description>ancient</description>
  <pubDate>Wed, 01 Jan 2020 08:00:00 GMT</pubDate>
</item>
</channel></rss>
```

`backend/tests/fixtures/hn_sample.json`:
```json
{"hits": [
  {"title": "Snyk lays off 10% of staff", "url": "https://news.example/snyk-layoffs",
   "objectID": "41001", "created_at_i": 1785744000},
  {"title": "Ask HN: Artifactory alternatives?", "url": null,
   "objectID": "41002", "created_at_i": 1785747600}
]}
```

`backend/tests/fixtures/reddit_sample.json`:
```json
{"data": {"children": [
  {"data": {"title": "GitLab 18.3 registry improvements", "permalink": "/r/devops/comments/x1/glab/",
            "selftext": "Release notes discussion", "created_utc": 1785744000, "over_18": false}}
]}}
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_adapters.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.sources.hackernews import fetch_hackernews
from app.sources.reddit import fetch_reddit
from app.sources.rss import fetch_rss
from app.sources.tavily import fetch_tavily

FIX = Path(__file__).parent / "fixtures"
WINDOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def client_returning(content: bytes, content_type: str) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": content_type})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_rss_parses_strips_html_and_windows():
    client = client_returning((FIX / "rss_sample.xml").read_bytes(), "application/rss+xml")
    items = await fetch_rss(client, "Sonatype Blog", "https://vendor.example/rss", WINDOW)
    assert len(items) == 1  # old post filtered by window
    it = items[0]
    assert it.title == "Nexus Repository 3.99 adds SBOM export"
    assert "<" not in it.body_excerpt and "SBOM export" in it.body_excerpt
    assert it.source_type == "rss" and it.published_at.year == 2026


async def test_hackernews_uses_hn_permalink_when_no_url():
    client = client_returning((FIX / "hn_sample.json").read_bytes(), "application/json")
    items = await fetch_hackernews(client, "snyk", WINDOW)
    assert len(items) == 2
    assert items[0].url == "https://news.example/snyk-layoffs"
    assert items[1].url == "https://news.ycombinator.com/item?id=41002"
    assert all(i.source_type == "hackernews" for i in items)


async def test_reddit_builds_permalink():
    client = client_returning((FIX / "reddit_sample.json").read_bytes(), "application/json")
    items = await fetch_reddit(client, ["devops"], "gitlab", WINDOW)
    assert items[0].url == "https://www.reddit.com/r/devops/comments/x1/glab"
    assert items[0].source_name == "Reddit r/devops"


async def test_tavily_posts_key_and_parses():
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"results": [
            {"title": "Docker updates pricing", "url": "https://t.example/d",
             "content": "Docker changed Hub pricing tiers.", "published_date": "2026-08-02"}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    items = await fetch_tavily(client, "key123", "Docker Hub news", WINDOW)
    assert captured["api_key"] == "key123" and captured["topic"] == "news"
    assert items[0].source_type == "tavily" and items[0].title.startswith("Docker")


async def test_adapter_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        await fetch_rss(client, "X", "https://x.example/rss", WINDOW)
        raised = False
    except httpx.HTTPStatusError:
        raised = True
    assert raised  # orchestrator (Task 12) is responsible for isolation
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_adapters.py -v`
Expected: FAIL — ModuleNotFoundError for the four adapter modules.

- [ ] **Step 4: Implement the adapters**

`backend/app/sources/rss.py`:
```python
import html
import re
from datetime import datetime, timezone

import feedparser
import httpx

from app.sources.base import USER_AGENT, RawItem

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).replace("\xa0", " ").split()  # noqa: E501 - joined below


def strip_html(s: str) -> str:
    return " ".join(_strip_html(s))


def _entry_date(e) -> datetime | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


async def fetch_rss(client: httpx.AsyncClient, name: str, url: str,
                    window_start: datetime) -> list[RawItem]:
    r = await client.get(url, timeout=20, headers=USER_AGENT, follow_redirects=True)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    items: list[RawItem] = []
    for e in feed.entries:
        published = _entry_date(e)
        if published and published < window_start:
            continue
        items.append(RawItem(
            title=(e.get("title") or "").strip(),
            url=e.get("link") or "",
            body_excerpt=strip_html(e.get("summary", ""))[:1000],
            source_name=name, source_type="rss", published_at=published))
    return items
```

`backend/app/sources/hackernews.py`:
```python
from datetime import datetime, timezone

import httpx

from app.sources.base import USER_AGENT, RawItem

API = "https://hn.algolia.com/api/v1/search_by_date"


async def fetch_hackernews(client: httpx.AsyncClient, query: str,
                           window_start: datetime) -> list[RawItem]:
    params = {"query": query, "tags": "story",
              "numericFilters": f"created_at_i>{int(window_start.timestamp())}",
              "hitsPerPage": 30}
    r = await client.get(API, params=params, timeout=20, headers=USER_AGENT)
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", []):
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
        items.append(RawItem(
            title=(h.get("title") or "").strip(), url=url,
            body_excerpt="", source_name="Hacker News", source_type="hackernews",
            published_at=datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc)))
    return items
```

`backend/app/sources/reddit.py`:
```python
from datetime import datetime, timezone

import httpx

from app.sources.base import USER_AGENT, RawItem


async def fetch_reddit(client: httpx.AsyncClient, subreddits: list[str], query: str,
                       window_start: datetime) -> list[RawItem]:
    items: list[RawItem] = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": query, "sort": "new", "t": "week", "limit": 25, "restrict_sr": 1}
        r = await client.get(url, params=params, timeout=20, headers=USER_AGENT)
        r.raise_for_status()
        for child in r.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            if d.get("over_18"):
                continue
            published = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if published < window_start:
                continue
            items.append(RawItem(
                title=(d.get("title") or "").strip(),
                url=f"https://www.reddit.com{d.get('permalink', '').rstrip('/')}",
                body_excerpt=(d.get("selftext") or "")[:1000],
                source_name=f"Reddit r/{sub}", source_type="reddit", published_at=published))
    return items
```

`backend/app/sources/tavily.py`:
```python
from datetime import datetime, timezone

import httpx

from app.sources.base import RawItem

API = "https://api.tavily.com/search"


async def fetch_tavily(client: httpx.AsyncClient, api_key: str, query: str,
                       window_start: datetime) -> list[RawItem]:
    days = max(1, (datetime.now(timezone.utc) - window_start).days)
    r = await client.post(API, json={"api_key": api_key, "query": query, "topic": "news",
                                     "days": days, "max_results": 10}, timeout=30)
    r.raise_for_status()
    items = []
    for res in r.json().get("results", []):
        published = None
        if res.get("published_date"):
            try:
                published = datetime.fromisoformat(res["published_date"]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        items.append(RawItem(title=(res.get("title") or "").strip(), url=res.get("url") or "",
                             body_excerpt=(res.get("content") or "")[:1000],
                             source_name="Tavily News", source_type="tavily",
                             published_at=published))
    return items
```

Note: `rss.py` defines both `_strip_html` (list of words) and `strip_html` (joined) — keep only the public `strip_html`; simplify to:
```python
def strip_html(s: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", s or "")).split())
```
(Delete the redundant `_strip_html`. The test guards behavior, not internals.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_adapters.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(sources): RSS/HN/Reddit/Tavily adapters with fixture tests"
```

---

### Task 8: Enrichment stage

**Files:**
- Create: `backend/app/pipeline/enrich.py`
- Modify: `backend/tests/conftest.py` (append FakeGateway)
- Test: `backend/tests/test_enrich.py`

- [ ] **Step 1: Append FakeGateway to conftest**

Append to `backend/tests/conftest.py`:
```python
class FakeGateway:
    """Queue of canned responses; records every call. None = simulated LLM failure."""

    def __init__(self, responses: list | None = None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str, str]] = []  # (schema_name, system, user)

    def complete_json(self, system: str, user: str, schema, temperature: float = 0.2):
        self.calls.append((schema.__name__, system, user))
        return self.responses.pop(0) if self.responses else None

    def available(self) -> bool:
        return True
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_enrich.py`:
```python
from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import Enrichment
from app.pipeline.enrich import enrich_new_articles
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_enrich_applies_fields_and_statuses(session):
    a1 = make_article(session, url="https://a.example/1", title="Snyk price hike")
    a2 = make_article(session, url="https://a.example/2", title="Kittens are cute")
    a3 = make_article(session, url="https://a.example/3", title="LLM broke")
    gw = FakeGateway([
        Enrichment(relevant=True, competitors=["snyk", "not_tracked"], domain="devsecops_scanning",
                   event_type="pricing_change", summary="s", jfrog_impact=4, so_what="w"),
        Enrichment(relevant=False, domain="other", event_type="other",
                   summary="", jfrog_impact=1, so_what=""),
        None,  # gateway failure
    ])
    n = enrich_new_articles(session, gw, appcfg())
    assert n == 2  # two successfully classified (one relevant, one irrelevant)

    session.refresh(a1); session.refresh(a2); session.refresh(a3)
    assert a1.status == "enriched" and a1.relevant is True
    assert a1.competitors == ["snyk"]           # unknown slug filtered out
    assert a1.jfrog_impact == 4 and a1.enriched_at is not None
    assert a2.status == "irrelevant" and a2.relevant is False
    assert a3.status == "failed"


def test_enrich_skips_non_new(session):
    make_article(session, url="https://a.example/4", title="done", status="enriched")
    gw = FakeGateway([])
    assert enrich_new_articles(session, gw, appcfg()) == 0
    assert gw.calls == []


def test_prompt_contains_slugs_and_title(session):
    make_article(session, url="https://a.example/5", title="GitLab ships thing")
    gw = FakeGateway([Enrichment(relevant=True, competitors=["gitlab"], domain="cicd",
                                 event_type="feature_update", summary="s",
                                 jfrog_impact=2, so_what="w")])
    enrich_new_articles(session, gw, appcfg())
    schema_name, system, user = gw.calls[0]
    assert schema_name == "Enrichment"
    assert "sonatype, gitlab, github, docker, snyk" in system
    assert "GitLab ships thing" in user
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_enrich.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.enrich'`.

- [ ] **Step 4: Implement**

`backend/app/pipeline/enrich.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import ENRICH_SYSTEM, ENRICH_USER
from app.llm.schemas import Enrichment
from app.models import Article, utcnow


def enrich_new_articles(session: Session, gateway, appcfg: AppConfig, limit: int = 200) -> int:
    system = ENRICH_SYSTEM.format(slugs=", ".join(appcfg.slugs()))
    known = set(appcfg.slugs())
    done = 0
    articles = session.scalars(
        select(Article).where(Article.status == "new").order_by(Article.id).limit(limit)).all()
    for a in articles:
        user = ENRICH_USER.format(title=a.title, source_name=a.source_name,
                                  source_type=a.source_type,
                                  published_at=a.published_at or "unknown",
                                  excerpt=a.body_excerpt[:800])
        enr: Enrichment | None = gateway.complete_json(system, user, Enrichment)
        if enr is None:
            a.status = "failed"
            continue
        a.relevant = enr.relevant
        if not enr.relevant:
            a.status = "irrelevant"
        else:
            a.competitors = [s for s in enr.competitors if s in known]
            a.domain = enr.domain
            a.event_type = enr.event_type
            a.summary = enr.summary
            a.jfrog_impact = enr.jfrog_impact
            a.so_what = enr.so_what
            a.status = "enriched"
            a.enriched_at = utcnow()
        done += 1
    session.commit()
    return done
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_enrich.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(pipeline): LLM enrichment stage with relevance gate"
```

---

### Task 9: Delta analysis stage

**Files:**
- Create: `backend/app/pipeline/delta.py`
- Test: `backend/tests/test_delta.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_delta.py`:
```python
from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import Delta
from app.pipeline.delta import run_delta_analysis
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def enriched(session, url, impact, **kw):
    return make_article(session, url=url, title=f"t{impact}", status="enriched",
                        relevant=True, competitors=["snyk"], domain="devsecops_scanning",
                        event_type="product_launch", summary="sum", jfrog_impact=impact,
                        so_what="w", **kw)


def test_delta_only_for_high_impact(session):
    high = enriched(session, "https://d.example/1", 4)
    enriched(session, "https://d.example/2", 3)
    gw = FakeGateway([Delta(competitor_move="m", jfrog_equivalent="Xray contextual analysis",
                            strategic_impact="high", talking_points=["a", "b"])])
    n = run_delta_analysis(session, gw, appcfg())
    assert n == 1 and len(gw.calls) == 1
    session.refresh(high)
    assert high.delta_strategic_impact == "high"
    assert high.delta_talking_points == ["a", "b"]
    _, system, _ = gw.calls[0]
    assert "Xray contextual analysis" in system  # capability sheet injected


def test_delta_idempotent_and_failsoft(session):
    a = enriched(session, "https://d.example/3", 5)
    a.delta_move = "already done"
    session.commit()
    b = enriched(session, "https://d.example/4", 5)
    gw = FakeGateway([None])  # LLM fails
    n = run_delta_analysis(session, gw, appcfg())
    assert n == 0 and len(gw.calls) == 1  # only b attempted, failed softly
    session.refresh(b)
    assert b.delta_move is None and b.status == "enriched"  # article stays usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_delta.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement**

`backend/app/pipeline/delta.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import DELTA_SYSTEM, DELTA_USER
from app.llm.schemas import Delta
from app.models import Article

DELTA_THRESHOLD = 4


def run_delta_analysis(session: Session, gateway, appcfg: AppConfig, limit: int = 25) -> int:
    system = DELTA_SYSTEM.format(capabilities=appcfg.capabilities_text())
    articles = session.scalars(
        select(Article).where(Article.status == "enriched",
                              Article.jfrog_impact >= DELTA_THRESHOLD,
                              Article.delta_move.is_(None))
        .order_by(Article.id).limit(limit)).all()
    done = 0
    for a in articles:
        user = DELTA_USER.format(competitors=", ".join(a.competitors or []),
                                 event_type=a.event_type, domain=a.domain,
                                 title=a.title, summary=a.summary or "")
        d: Delta | None = gateway.complete_json(system, user, Delta)
        if d is None:
            continue
        a.delta_move = d.competitor_move
        a.delta_jfrog_equivalent = d.jfrog_equivalent
        a.delta_strategic_impact = d.strategic_impact
        a.delta_talking_points = d.talking_points
        done += 1
    session.commit()
    return done
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_delta.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(pipeline): capability-sheet-grounded delta analysis for high-impact items"
```

---

### Task 10: Daily digest stage

**Files:**
- Create: `backend/app/pipeline/digest.py`
- Test: `backend/tests/test_digest.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_digest.py`:
```python
from datetime import datetime, timezone

from app.llm.schemas import Claim, CompetitorSection, DigestSchema, TypedClaim
from app.models import Digest
from app.pipeline.digest import generate_digest
from tests.conftest import FakeGateway, make_article


def test_no_items_writes_quiet_digest_without_llm(session):
    gw = FakeGateway([])
    d = generate_digest(session, gw, date="2026-08-03")
    assert d.exec_summary.startswith("No significant")
    assert gw.calls == []
    assert session.query(Digest).filter_by(date="2026-08-03").count() == 1


def test_digest_enforces_citations_and_upserts(session):
    a = make_article(session, url="https://g.example/1", title="A", status="enriched",
                     relevant=True, competitors=["snyk"], jfrog_impact=4, summary="s",
                     domain="devsecops_scanning", event_type="product_launch", so_what="w",
                     fetched_at=datetime(2026, 8, 3, 10, tzinfo=timezone.utc))
    raw = DigestSchema(
        exec_summary="Busy day.",
        top_developments=[Claim(text="real", article_ids=[a.id]),
                          Claim(text="hallucinated", article_ids=[999])],
        by_competitor=[CompetitorSection(competitor="snyk",
                                         highlights=[Claim(text="h", article_ids=[a.id])])],
        threats_opportunities=[TypedClaim(kind="threat", text="t", article_ids=[999])])
    gw = FakeGateway([raw])
    generate_digest(session, gw, date="2026-08-03")

    row = session.query(Digest).filter_by(date="2026-08-03").one()
    assert [c["text"] for c in row.sections["top_developments"]] == ["real"]
    assert row.sections["threats_opportunities"] == []
    _, system, user = gw.calls[0]
    assert f"[{a.id}]" in user and "CITATION RULE" in system

    # regeneration same date replaces, not duplicates
    gw2 = FakeGateway([raw])
    generate_digest(session, gw2, date="2026-08-03")
    assert session.query(Digest).filter_by(date="2026-08-03").count() == 1


def test_llm_failure_keeps_old_digest(session):
    make_article(session, url="https://g.example/2", title="B", status="enriched",
                 relevant=True, competitors=["gitlab"], jfrog_impact=3, summary="s",
                 domain="cicd", event_type="feature_update", so_what="w",
                 fetched_at=datetime(2026, 8, 3, 11, tzinfo=timezone.utc))
    gw = FakeGateway([None])
    d = generate_digest(session, gw, date="2026-08-03")
    assert d is None  # failed, nothing written
    assert session.query(Digest).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_digest.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement**

`backend/app/pipeline/digest.py`:
```python
from datetime import date as date_cls
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.prompts import DIGEST_SYSTEM, DIGEST_USER
from app.llm.schemas import DigestSchema, enforce_digest_citations
from app.models import Article, Digest, utcnow


def _items_for(session: Session, date: str) -> list[Article]:
    day = date_cls.fromisoformat(date)
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return list(session.scalars(select(Article).where(
        Article.status == "enriched", Article.relevant.is_(True),
        Article.fetched_at >= start, Article.fetched_at <= end)
        .order_by(Article.jfrog_impact.desc())))


def _upsert(session: Session, date: str, exec_summary: str, sections: dict, model: str) -> Digest:
    row = session.scalar(select(Digest).where(Digest.date == date))
    if row is None:
        row = Digest(date=date, exec_summary=exec_summary, sections=sections, model_used=model)
        session.add(row)
    else:
        row.exec_summary, row.sections, row.model_used = exec_summary, sections, model
        row.generated_at = utcnow()
    session.commit()
    return row


def generate_digest(session: Session, gateway, date: str, model_label: str = "") -> Digest | None:
    items = _items_for(session, date)
    if not items:
        return _upsert(session, date,
                       "No significant competitive developments detected today.",
                       {"top_developments": [], "by_competitor": [], "threats_opportunities": []},
                       model_label)
    lines = [f"[{a.id}] ({', '.join(a.competitors or [])} | {a.domain} | {a.event_type} "
             f"| impact {a.jfrog_impact}) {a.summary} SO-WHAT: {a.so_what}" for a in items]
    raw: DigestSchema | None = gateway.complete_json(
        DIGEST_SYSTEM, DIGEST_USER.format(date=date, items="\n".join(lines)), DigestSchema)
    if raw is None:
        return None
    clean = enforce_digest_citations(raw, valid_ids={a.id for a in items})
    return _upsert(session, date, clean.exec_summary,
                   clean.model_dump(exclude={"exec_summary"}), model_label)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_digest.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(pipeline): daily digest with schema-enforced citations"
```

---

### Task 11: Battlecard stage

**Files:**
- Create: `backend/app/pipeline/battlecard.py`
- Test: `backend/tests/test_battlecard.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_battlecard.py`:
```python
from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import BattlecardGen, Claim
from app.models import Battlecard
from app.pipeline.battlecard import refresh_battlecards
from tests.conftest import FakeGateway, make_article


def appcfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_refresh_only_competitors_with_news(session):
    a = make_article(session, url="https://b.example/1", title="Snyk news", status="enriched",
                     relevant=True, competitors=["snyk"], jfrog_impact=3, summary="s",
                     domain="devsecops_scanning", event_type="feature_update", so_what="w")
    gw = FakeGateway([BattlecardGen(recent_moves=[
        Claim(text="cited move", article_ids=[a.id]),
        Claim(text="uncited move", article_ids=[777])])])
    n = refresh_battlecards(session, gw, appcfg())
    assert n == 1 and len(gw.calls) == 1  # only snyk had items
    card = session.query(Battlecard).filter_by(competitor_slug="snyk").one()
    assert [m["text"] for m in card.recent_moves] == ["cited move"]


def test_refresh_upserts_and_failsoft(session):
    make_article(session, url="https://b.example/2", title="GitLab news", status="enriched",
                 relevant=True, competitors=["gitlab"], jfrog_impact=2, summary="s",
                 domain="cicd", event_type="feature_update", so_what="w")
    session.add(Battlecard(competitor_slug="gitlab",
                           recent_moves=[{"text": "old", "article_ids": [1]}]))
    session.commit()
    gw = FakeGateway([None])  # LLM fails
    n = refresh_battlecards(session, gw, appcfg())
    assert n == 0
    card = session.query(Battlecard).filter_by(competitor_slug="gitlab").one()
    assert card.recent_moves[0]["text"] == "old"  # untouched on failure
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_battlecard.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement**

`backend/app/pipeline/battlecard.py`:
```python
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_data import AppConfig
from app.llm.prompts import BATTLECARD_SYSTEM, BATTLECARD_USER
from app.llm.schemas import BattlecardGen, enforce_battlecard_citations
from app.models import Article, Battlecard, utcnow

LOOKBACK_DAYS = 14
MAX_ITEMS = 15


def refresh_battlecards(session: Session, gateway, appcfg: AppConfig) -> int:
    since = utcnow() - timedelta(days=LOOKBACK_DAYS)
    updated = 0
    for comp in appcfg.competitors:
        slug, name = comp["slug"], comp["name"]
        items = list(session.scalars(select(Article).where(
            Article.status == "enriched", Article.relevant.is_(True),
            Article.fetched_at >= since)
            .order_by(Article.jfrog_impact.desc()).limit(200)))
        items = [a for a in items if slug in (a.competitors or [])][:MAX_ITEMS]
        if not items:
            continue
        lines = [f"[{a.id}] ({a.event_type}, impact {a.jfrog_impact}) {a.summary}" for a in items]
        gen: BattlecardGen | None = gateway.complete_json(
            BATTLECARD_SYSTEM.format(name=name),
            BATTLECARD_USER.format(name=name, items="\n".join(lines)), BattlecardGen)
        if gen is None:
            continue
        moves = enforce_battlecard_citations(gen.recent_moves, {a.id for a in items})
        card = session.scalar(select(Battlecard).where(Battlecard.competitor_slug == slug))
        if card is None:
            card = Battlecard(competitor_slug=slug)
            session.add(card)
        card.recent_moves = [m.model_dump() for m in moves]
        card.generated_at = utcnow()
        updated += 1
    session.commit()
    return updated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_battlecard.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(pipeline): citation-enforced battlecard recent-moves refresh"
```

---

### Task 12: Pipeline orchestrator (fetch concurrency, isolation, run state)

**Files:**
- Create: `backend/app/pipeline/run.py`
- Test: `backend/tests/test_run_pipeline.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_run_pipeline.py`:
```python
import httpx

from app.config import Settings
from app.config_data import AppConfig
from app.llm.schemas import BattlecardGen, Claim, Delta, DigestSchema, Enrichment
from app.models import Article, SourceRun
from app.pipeline.run import REFRESH_STATE, run_pipeline
from tests.conftest import FakeGateway

RSS = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
       b'<item><title>Sonatype ships SBOM thing</title>'
       b'<link>https://vendor.example/p1</link><description>d</description>'
       b'<pubDate>Mon, 03 Aug 2026 08:00:00 GMT</pubDate></item></channel></rss>')


def make_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "hn.algolia.com":
            return httpx.Response(200, json={"hits": []})
        if host == "www.reddit.com":
            return httpx.Response(500)  # one failing source must not kill the run
        return httpx.Response(200, content=RSS,
                              headers={"content-type": "application/rss+xml"})
    return httpx.MockTransport(handler)


def one_competitor_cfg() -> AppConfig:
    cfg = AppConfig.load(Settings(_env_file=None).config_dir)
    cfg.competitors = [c for c in cfg.competitors if c["slug"] == "sonatype"]
    cfg.industry_feeds = []
    return cfg


async def test_pipeline_end_to_end_with_isolation(session_factory):
    enr = Enrichment(relevant=True, competitors=["sonatype"], domain="artifact_management",
                     event_type="product_launch", summary="s", jfrog_impact=4, so_what="w")
    gw = FakeGateway([
        enr,
        Delta(competitor_move="m", jfrog_equivalent="Artifactory universal repository",
              strategic_impact="high", talking_points=["t"]),
        DigestSchema(exec_summary="day", top_developments=[Claim(text="c", article_ids=[1])],
                     by_competitor=[], threats_opportunities=[]),
        BattlecardGen(recent_moves=[Claim(text="mv", article_ids=[1])]),
    ])
    report = await run_pipeline(session_factory, Settings(_env_file=None), one_competitor_cfg(),
                                gw, transport=make_transport())
    assert report["inserted"] == 1 and report["enriched"] == 1
    assert REFRESH_STATE["running"] is False and REFRESH_STATE["stage"] == "done"

    with session_factory() as s:
        assert s.query(Article).count() == 1
        runs = s.query(SourceRun).all()
        assert any(not r.ok and "reddit" in r.source_name.lower() for r in runs)
        assert any(r.ok and r.items_found == 1 for r in runs)


async def test_pipeline_skips_llm_stages_without_gateway_availability(session_factory):
    class DeadGateway(FakeGateway):
        def available(self) -> bool:
            return False
    report = await run_pipeline(session_factory, Settings(_env_file=None), one_competitor_cfg(),
                                DeadGateway(), transport=make_transport())
    assert report["inserted"] == 1 and report["enriched"] == 0
    assert "LLM unavailable" in " ".join(REFRESH_STATE["errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_pipeline.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement**

`backend/app/pipeline/run.py`:
```python
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings
from app.config_data import AppConfig
from app.models import SourceRun, utcnow
from app.pipeline.battlecard import refresh_battlecards
from app.pipeline.dedupe import insert_new_items
from app.pipeline.delta import run_delta_analysis
from app.pipeline.digest import generate_digest
from app.pipeline.enrich import enrich_new_articles
from app.sources.hackernews import fetch_hackernews
from app.sources.reddit import fetch_reddit
from app.sources.rss import fetch_rss
from app.sources.tavily import fetch_tavily

log = logging.getLogger("ribbit.pipeline")

REFRESH_STATE: dict = {"running": False, "stage": "idle", "counts": {}, "errors": [],
                       "started_at": None, "finished_at": None}


def _tasks_for(client, settings: Settings, appcfg: AppConfig, window: datetime):
    tasks: list[tuple[str, object]] = []
    for comp in appcfg.competitors:
        src = comp["sources"]
        for url in src.get("rss", []):
            tasks.append((f"{comp['name']} RSS", fetch_rss(client, f"{comp['name']} Blog", url, window)))
        if src.get("hn_query"):
            tasks.append((f"{comp['name']} HackerNews",
                          fetch_hackernews(client, src["hn_query"], window)))
        if src.get("reddit"):
            tasks.append((f"{comp['name']} Reddit",
                          fetch_reddit(client, src["reddit"].get("subreddits", []),
                                       src["reddit"].get("query", comp["name"]), window)))
        tavily_key = settings.tavily_api_key.get_secret_value()
        if tavily_key and src.get("tavily_query"):
            tasks.append((f"{comp['name']} Tavily",
                          fetch_tavily(client, tavily_key, src["tavily_query"], window)))
    for feed in appcfg.industry_feeds:
        tasks.append((feed["name"], fetch_rss(client, feed["name"], feed["url"], window)))
    return tasks


async def run_pipeline(session_factory, settings: Settings, appcfg: AppConfig, gateway,
                       transport: httpx.BaseTransport | None = None) -> dict:
    run_id = uuid.uuid4().hex[:8]
    REFRESH_STATE.update(running=True, stage="fetching", counts={}, errors=[],
                         started_at=utcnow().isoformat(), finished_at=None)
    window = datetime.now(timezone.utc) - timedelta(days=settings.fetch_window_days)
    report = {"inserted": 0, "enriched": 0, "deltas": 0, "battlecards": 0}
    try:
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            named = _tasks_for(client, settings, appcfg, window)
            results = await asyncio.gather(*(t for _, t in named), return_exceptions=True)
        items = []
        with session_factory() as s:
            for (name, _), res in zip(named, results):
                if isinstance(res, BaseException):
                    s.add(SourceRun(run_id=run_id, source_name=name, ok=False, error=str(res)))
                    REFRESH_STATE["errors"].append(f"{name}: {res}")
                else:
                    s.add(SourceRun(run_id=run_id, source_name=name, ok=True,
                                    items_found=len(res)))
                    items.extend(res)
            s.commit()
            report["inserted"] = insert_new_items(s, items)
            REFRESH_STATE["counts"]["inserted"] = report["inserted"]

            if not gateway.available():
                REFRESH_STATE["errors"].append("LLM unavailable - enrichment skipped")
            else:
                REFRESH_STATE["stage"] = "enriching"
                report["enriched"] = enrich_new_articles(s, gateway, appcfg)
                REFRESH_STATE["stage"] = "delta"
                report["deltas"] = run_delta_analysis(s, gateway, appcfg)
                REFRESH_STATE["stage"] = "digest"
                today = datetime.now(timezone.utc).date().isoformat()
                generate_digest(s, gateway, today,
                                model_label=f"{settings.llm_provider}/{settings.llm_model}")
                REFRESH_STATE["stage"] = "battlecards"
                report["battlecards"] = refresh_battlecards(s, gateway, appcfg)
            REFRESH_STATE["counts"].update(report)
        REFRESH_STATE["stage"] = "done"
    except Exception as e:  # belt-and-braces: never leave state stuck on running
        log.exception("pipeline crashed")
        REFRESH_STATE["errors"].append(str(e))
        REFRESH_STATE["stage"] = "error"
    finally:
        REFRESH_STATE["running"] = False
        REFRESH_STATE["finished_at"] = utcnow().isoformat()
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_pipeline.py -v`
Expected: 2 passed. Also run the whole suite: `pytest -q` — all green.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(pipeline): concurrent isolated fetch + full-run orchestrator with state"
```

---

### Task 13: Read API (articles, digest, competitors, matrix, meta, sources)

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/deps.py`, `backend/app/api/routes_read.py`, `backend/app/main.py`
- Test: `backend/tests/test_api_read.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_read.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Battlecard, Digest
from tests.conftest import FakeGateway, make_article


@pytest.fixture()
def client(tmp_path, session_factory, engine):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/api.db",
                        demo_mode="off", enable_scheduler=False)
    app = create_app(settings)
    app.state.session_factory = session_factory   # inject test DB
    app.state.gateway = FakeGateway()
    with TestClient(app) as c:
        yield c


def seed(session):
    a = make_article(session, url="https://s.example/1", title="Snyk pricing move",
                     status="enriched", relevant=True, competitors=["snyk"],
                     domain="devsecops_scanning", event_type="pricing_change",
                     summary="Snyk raised prices.", jfrog_impact=4, so_what="displacement window",
                     delta_move="m", delta_jfrog_equivalent="Xray", delta_strategic_impact="high",
                     delta_talking_points=["t1"])
    make_article(session, url="https://s.example/2", title="GitLab minor", status="enriched",
                 relevant=True, competitors=["gitlab"], domain="cicd",
                 event_type="feature_update", summary="s", jfrog_impact=2, so_what="w")
    session.add(Digest(date="2026-08-03", exec_summary="busy",
                       sections={"top_developments": [{"text": "c", "article_ids": [a.id]}],
                                 "by_competitor": [], "threats_opportunities": []},
                       model_used="test"))
    session.add(Battlecard(competitor_slug="snyk",
                           recent_moves=[{"text": "mv", "article_ids": [a.id]}]))
    session.commit()
    return a


def test_articles_filters(client, session):
    seed(session)
    r = client.get("/api/articles", params={"competitor": "snyk", "min_impact": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    art = body["items"][0]
    assert art["title"] == "Snyk pricing move"
    assert art["delta"]["strategic_impact"] == "high"

    assert client.get("/api/articles", params={"event_type": "feature_update"}).json()["total"] == 1
    assert client.get("/api/articles", params={"q": "pricing"}).json()["total"] == 1


def test_digest_with_resolved_articles(client, session):
    a = seed(session)
    r = client.get("/api/digest")
    assert r.status_code == 200
    d = r.json()
    assert d["date"] == "2026-08-03" and d["exec_summary"] == "busy"
    assert d["articles"][str(a.id)]["url"] == "https://s.example/1"
    assert client.get("/api/digest/dates").json() == ["2026-08-03"]
    assert client.get("/api/digest", params={"date": "1999-01-01"}).status_code == 404


def test_competitors_and_battlecard(client, session):
    a = seed(session)
    comps = client.get("/api/competitors").json()
    snyk = next(c for c in comps if c["slug"] == "snyk")
    assert snyk["article_count"] == 1 and snyk["high_impact_count"] == 1
    card = client.get("/api/competitors/snyk/battlecard").json()
    assert card["base"]["strengths"] and card["recent_moves"][0]["text"] == "mv"
    assert card["articles"][str(a.id)]["title"] == "Snyk pricing move"
    assert client.get("/api/competitors/nope/battlecard").status_code == 404


def test_matrix_meta_sources(client, session):
    m = client.get("/api/matrix").json()
    assert m["vendors"][0] == "jfrog" and len(m["rows"]) >= 6
    meta = client.get("/api/meta").json()
    assert meta["demo_mode"] is False and "provider" in meta
    assert client.get("/api/sources/health").json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_read.py -v`
Expected: FAIL — ModuleNotFoundError (app.api / app.main).

- [ ] **Step 3: Implement deps, routes, and a minimal create_app**

`backend/app/api/__init__.py`: empty file.

`backend/app/api/deps.py`:
```python
from fastapi import Request


def get_session_factory(request: Request):
    return request.app.state.session_factory


def get_settings(request: Request):
    return request.app.state.settings


def get_appcfg(request: Request):
    return request.app.state.appcfg


def get_gateway(request: Request):
    return request.app.state.gateway
```

`backend/app/api/routes_read.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, text

from app.api.deps import get_appcfg, get_session_factory, get_settings
from app.models import Article, Battlecard, Digest, SourceRun
from app.pipeline.run import REFRESH_STATE

router = APIRouter(prefix="/api")


def _article_dict(a: Article) -> dict:
    d = {"id": a.id, "title": a.title, "url": a.url, "source_name": a.source_name,
         "source_type": a.source_type,
         "published_at": a.published_at.isoformat() if a.published_at else None,
         "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
         "competitors": a.competitors or [], "domain": a.domain, "event_type": a.event_type,
         "summary": a.summary, "jfrog_impact": a.jfrog_impact, "so_what": a.so_what,
         "delta": None}
    if a.delta_move:
        d["delta"] = {"move": a.delta_move, "jfrog_equivalent": a.delta_jfrog_equivalent,
                      "strategic_impact": a.delta_strategic_impact,
                      "talking_points": a.delta_talking_points or []}
    return d


def _ref(a: Article) -> dict:
    return {"id": a.id, "title": a.title, "url": a.url,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "source_name": a.source_name}


def _resolve(session, sections: dict | list) -> dict:
    ids: set[int] = set()

    def walk(node):
        if isinstance(node, dict):
            ids.update(node.get("article_ids", []) if isinstance(node.get("article_ids"), list) else [])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(sections)
    if not ids:
        return {}
    rows = session.scalars(select(Article).where(Article.id.in_(ids))).all()
    return {str(a.id): _ref(a) for a in rows}


@router.get("/articles")
def list_articles(competitor: str | None = None, domain: str | None = None,
                  event_type: str | None = None, min_impact: int = 1,
                  q: str | None = None, page: int = 1, page_size: int = Query(20, le=100),
                  sf=Depends(get_session_factory)):
    with sf() as session:
        stmt = select(Article).where(Article.status == "enriched", Article.relevant.is_(True))
        if domain:
            stmt = stmt.where(Article.domain == domain)
        if event_type:
            stmt = stmt.where(Article.event_type == event_type)
        if min_impact > 1:
            stmt = stmt.where(Article.jfrog_impact >= min_impact)
        if q:
            fts = text("SELECT rowid FROM articles_fts WHERE articles_fts MATCH :q")
            hit_ids = [r[0] for r in session.execute(fts, {"q": f'"{q}"'})]
            stmt = stmt.where(Article.id.in_(hit_ids or [-1]))
        rows = list(session.scalars(stmt.order_by(desc(Article.fetched_at))))
        if competitor:
            rows = [a for a in rows if competitor in (a.competitors or [])]
        total = len(rows)
        rows = rows[(page - 1) * page_size: page * page_size]
        return {"items": [_article_dict(a) for a in rows], "total": total,
                "page": page, "page_size": page_size}


@router.get("/digest")
def get_digest(date: str | None = None, sf=Depends(get_session_factory)):
    with sf() as session:
        stmt = select(Digest)
        stmt = stmt.where(Digest.date == date) if date else stmt.order_by(desc(Digest.date))
        row = session.scalars(stmt).first()
        if row is None:
            raise HTTPException(404, "no digest for that date")
        return {"date": row.date, "exec_summary": row.exec_summary, "sections": row.sections,
                "generated_at": row.generated_at.isoformat(), "model_used": row.model_used,
                "articles": _resolve(session, row.sections)}


@router.get("/digest/dates")
def digest_dates(sf=Depends(get_session_factory)):
    with sf() as session:
        return [d for (d,) in session.execute(select(Digest.date).order_by(desc(Digest.date)))]


@router.get("/competitors")
def competitors(sf=Depends(get_session_factory), appcfg=Depends(get_appcfg)):
    with sf() as session:
        rows = session.scalars(select(Article).where(
            Article.status == "enriched", Article.relevant.is_(True))).all()
        out = []
        for c in appcfg.competitors:
            mine = [a for a in rows if c["slug"] in (a.competitors or [])]
            last = max((a.fetched_at for a in mine), default=None)
            out.append({"slug": c["slug"], "name": c["name"], "color": c["color"],
                        "article_count": len(mine),
                        "high_impact_count": sum(1 for a in mine if (a.jfrog_impact or 0) >= 4),
                        "last_activity": last.isoformat() if last else None})
        return out


@router.get("/competitors/{slug}/battlecard")
def battlecard(slug: str, sf=Depends(get_session_factory), appcfg=Depends(get_appcfg)):
    comp = appcfg.competitor_by_slug(slug)
    if comp is None:
        raise HTTPException(404, "unknown competitor")
    with sf() as session:
        card = session.scalar(select(Battlecard).where(Battlecard.competitor_slug == slug))
        moves = card.recent_moves if card else []
        return {"slug": slug, "name": comp["name"], "color": comp["color"],
                "base": comp["battlecard_base"], "recent_moves": moves,
                "generated_at": card.generated_at.isoformat() if card else None,
                "articles": _resolve(session, moves)}


@router.get("/matrix")
def matrix(appcfg=Depends(get_appcfg)):
    return appcfg.matrix


@router.get("/meta")
def meta(request_settings=Depends(get_settings), sf=Depends(get_session_factory),
         appcfg=Depends(get_appcfg)):
    from app.main import DEMO_FLAG
    with sf() as session:
        last = session.scalar(select(SourceRun.started_at).order_by(desc(SourceRun.started_at)))
    return {"provider": request_settings.llm_provider, "model": request_settings.llm_model,
            "demo_mode": DEMO_FLAG["on"], "refresh_hour": request_settings.refresh_hour,
            "last_refresh": last.isoformat() if last else None,
            "competitors": len(appcfg.competitors), "version": "0.1.0",
            "refresh_state": REFRESH_STATE}


@router.get("/sources/health")
def sources_health(sf=Depends(get_session_factory)):
    with sf() as session:
        rows = session.scalars(select(SourceRun).order_by(desc(SourceRun.id)).limit(200)).all()
        latest: dict[str, SourceRun] = {}
        for r in rows:
            latest.setdefault(r.source_name, r)
        return [{"source_name": r.source_name, "ok": r.ok, "items_found": r.items_found,
                 "error": r.error, "started_at": r.started_at.isoformat()}
                for r in latest.values()]
```

`backend/app/main.py` (minimal now; refresh/scheduler/demo wiring lands in Tasks 14-15):
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_read import router as read_router
from app.config import Settings
from app.config_data import AppConfig
from app.llm.gateway import LLMGateway
from app.models import init_db

DEMO_FLAG = {"on": False}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings.database_url)
        init_db(engine)
        # don't clobber test-injected doubles
        if not hasattr(app.state, "session_factory"):
            app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        if not hasattr(app.state, "gateway"):
            app.state.gateway = LLMGateway(settings)
        yield

    app = FastAPI(title="Ribbit", lifespan=lifespan)
    app.state.settings = settings
    app.state.appcfg = AppConfig.load(settings.config_dir)
    app.include_router(read_router)
    return app
```

Note: `create_app` sets `settings`/`appcfg` eagerly (available before lifespan) and DB/gateway lazily in lifespan. Timing that makes the tests work: tests inject `session_factory`/`gateway` on `app.state` after `create_app()` but before `TestClient(app)` context entry — lifespan runs at context entry, and its `hasattr` guards preserve the injected doubles.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_read.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(api): read endpoints with citation resolution + app factory"
```

---

### Task 14: Refresh endpoints + scheduler wiring

**Files:**
- Create: `backend/app/api/routes_admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_admin.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_admin.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline.run import REFRESH_STATE
from tests.conftest import FakeGateway


@pytest.fixture()
def client(tmp_path, session_factory):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/adm.db",
                        demo_mode="off", enable_scheduler=False)
    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.gateway = FakeGateway()
    with TestClient(app) as c:
        yield c


def test_refresh_status_reflects_state(client):
    REFRESH_STATE.update(running=False, stage="idle", errors=[])
    r = client.get("/api/refresh/status")
    assert r.status_code == 200 and r.json()["stage"] == "idle"


def test_refresh_conflict_while_running(client):
    REFRESH_STATE["running"] = True
    try:
        assert client.post("/api/refresh").status_code == 409
    finally:
        REFRESH_STATE["running"] = False


def test_refresh_starts_background_run(client, monkeypatch):
    called = {}

    async def fake_run(sf, settings, appcfg, gateway):
        called["yes"] = True
        return {"inserted": 0}
    monkeypatch.setattr("app.api.routes_admin.run_pipeline", fake_run)
    r = client.post("/api/refresh")
    assert r.status_code == 202 and r.json()["started"] is True
    assert called.get("yes") is True  # TestClient runs background tasks on response


def test_refresh_blocked_in_demo_mode(client):
    from app.main import DEMO_FLAG
    DEMO_FLAG["on"] = True
    try:
        r = client.post("/api/refresh")
        assert r.status_code == 409 and "demo" in r.json()["detail"].lower()
    finally:
        DEMO_FLAG["on"] = False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_admin.py -v`
Expected: FAIL — ModuleNotFoundError (routes_admin) / 404s.

- [ ] **Step 3: Implement admin routes and wire scheduler**

`backend/app/api/routes_admin.py`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_appcfg, get_gateway, get_session_factory, get_settings
from app.pipeline.run import REFRESH_STATE, run_pipeline

router = APIRouter(prefix="/api")


@router.post("/refresh", status_code=202)
async def trigger_refresh(background: BackgroundTasks,
                          sf=Depends(get_session_factory), settings=Depends(get_settings),
                          appcfg=Depends(get_appcfg), gateway=Depends(get_gateway)):
    from app.main import DEMO_FLAG
    if DEMO_FLAG["on"]:
        raise HTTPException(409, "Refresh is disabled in demo mode (no LLM provider configured)")
    if REFRESH_STATE["running"]:
        raise HTTPException(409, "A refresh is already running")
    background.add_task(run_pipeline, sf, settings, appcfg, gateway)
    return {"started": True}


@router.get("/refresh/status")
def refresh_status():
    return REFRESH_STATE
```

Modify `backend/app/main.py` — replace the whole file with:
```python
import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_admin import router as admin_router
from app.api.routes_read import router as read_router
from app.config import Settings
from app.config_data import AppConfig
from app.llm.gateway import LLMGateway
from app.models import init_db
from app.pipeline.run import REFRESH_STATE, run_pipeline

log = logging.getLogger("ribbit")
DEMO_FLAG = {"on": False}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings.database_url)
        init_db(engine)
        if not hasattr(app.state, "session_factory"):
            app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        if not hasattr(app.state, "gateway"):
            app.state.gateway = LLMGateway(settings)

        from app.demo import maybe_enter_demo_mode  # Task 15
        DEMO_FLAG["on"] = maybe_enter_demo_mode(app.state.session_factory,
                                                app.state.gateway, settings)

        scheduler = None
        if settings.enable_scheduler and not DEMO_FLAG["on"]:
            scheduler = AsyncIOScheduler()

            async def scheduled_run():
                if not REFRESH_STATE["running"]:
                    await run_pipeline(app.state.session_factory, settings,
                                       app.state.appcfg, app.state.gateway)

            scheduler.add_job(scheduled_run,
                              CronTrigger(hour=settings.refresh_hour, minute=0))
            scheduler.start()
            log.info("daily refresh scheduled at %02d:00", settings.refresh_hour)
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Ribbit", lifespan=lifespan)
    app.state.settings = settings
    app.state.appcfg = AppConfig.load(settings.config_dir)
    app.include_router(read_router)
    app.include_router(admin_router)
    return app
```

Also create a stub so imports resolve until Task 15 (immediately replaced there): `backend/app/demo.py`:
```python
def maybe_enter_demo_mode(session_factory, gateway, settings) -> bool:
    if settings.demo_mode == "on":
        return True
    if settings.demo_mode == "off":
        return False
    return not gateway.available()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_admin.py tests/test_api_read.py -v`
Expected: 8 passed (admin 4 + read 4 still green).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(api): refresh trigger/status endpoints + daily scheduler"
```

---

### Task 15: Demo mode with seed loading + starter seed

**Files:**
- Create: `data/demo/seed.json`, `scripts/capture_seed.py`
- Modify: `backend/app/demo.py`
- Test: `backend/tests/test_demo.py`

- [ ] **Step 1: Create the starter seed**

`data/demo/seed.json` — clearly-synthetic starter (replaced with real captured data in Task 24; `source_type: "demo"` and `[Sample]` markers keep it honest):
```json
{
  "articles": [
    {"id": 1, "url": "https://www.sonatype.com/blog", "title": "[Sample] Sonatype adds SBOM export to Nexus Repository",
     "body_excerpt": "Sample item for keyless demo mode.", "source_name": "Sonatype Blog (sample)",
     "source_type": "demo", "published_at": "2026-08-02T08:00:00+00:00",
     "fetched_at": "2026-08-03T07:00:00+00:00", "status": "enriched", "relevant": true,
     "competitors": ["sonatype"], "domain": "sbom_supply_chain", "event_type": "feature_update",
     "summary": "Sonatype announced SBOM export for repository artifacts.",
     "jfrog_impact": 4, "so_what": "Closes a gap vs JFrog's SBOM story; sharpen differentiation on distribution.",
     "delta_move": "Sonatype shipped SBOM export.",
     "delta_jfrog_equivalent": "SBOM generation & export (CycloneDX/SPDX) already ships with build-info provenance.",
     "delta_strategic_impact": "medium",
     "delta_talking_points": ["JFrog SBOMs are tied to build provenance", "Distribution signs release bundles end-to-end"]},
    {"id": 2, "url": "https://about.gitlab.com/releases", "title": "[Sample] GitLab 18.3 improves container registry cleanup policies",
     "body_excerpt": "Sample item for keyless demo mode.", "source_name": "GitLab Releases (sample)",
     "source_type": "demo", "published_at": "2026-08-02T10:00:00+00:00",
     "fetched_at": "2026-08-03T07:00:00+00:00", "status": "enriched", "relevant": true,
     "competitors": ["gitlab"], "domain": "container_registry", "event_type": "feature_update",
     "summary": "GitLab improved registry storage cleanup automation.",
     "jfrog_impact": 2, "so_what": "Registry parity marketing; no strategic shift."},
    {"id": 3, "url": "https://snyk.io/blog", "title": "[Sample] Snyk announces enterprise pricing changes",
     "body_excerpt": "Sample item for keyless demo mode.", "source_name": "Snyk Blog (sample)",
     "source_type": "demo", "published_at": "2026-08-03T06:00:00+00:00",
     "fetched_at": "2026-08-03T07:00:00+00:00", "status": "enriched", "relevant": true,
     "competitors": ["snyk"], "domain": "devsecops_scanning", "event_type": "pricing_change",
     "summary": "Snyk restructured enterprise tier pricing.",
     "jfrog_impact": 4, "so_what": "Renewal displacement window for Xray bundles.",
     "delta_move": "Snyk changed enterprise pricing.",
     "delta_jfrog_equivalent": "Xray SCA scanning bundled with Artifactory subscriptions.",
     "delta_strategic_impact": "high",
     "delta_talking_points": ["Bundle economics beat per-dev pricing at scale"]}
  ],
  "digests": [
    {"date": "2026-08-03", "exec_summary": "[Sample] Quiet-but-notable day: Sonatype closes an SBOM gap while Snyk's pricing shift opens a displacement window.",
     "sections": {
       "top_developments": [
         {"text": "Sonatype ships SBOM export, narrowing a differentiation gap.", "article_ids": [1]},
         {"text": "Snyk enterprise pricing restructure creates renewal-displacement opportunity.", "article_ids": [3]}],
       "by_competitor": [
         {"competitor": "sonatype", "highlights": [{"text": "SBOM export shipped.", "article_ids": [1]}]},
         {"competitor": "snyk", "highlights": [{"text": "Enterprise pricing changed.", "article_ids": [3]}]}],
       "threats_opportunities": [
         {"kind": "threat", "text": "Sonatype SBOM parity messaging.", "article_ids": [1]},
         {"kind": "opportunity", "text": "Snyk pricing turbulence at renewal time.", "article_ids": [3]}]},
     "model_used": "demo-seed"}
  ],
  "battlecards": [
    {"competitor_slug": "sonatype", "recent_moves": [{"text": "Shipped SBOM export.", "article_ids": [1]}]},
    {"competitor_slug": "snyk", "recent_moves": [{"text": "Restructured enterprise pricing.", "article_ids": [3]}]}
  ]
}
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_demo.py`:
```python
import json

from app.config import Settings
from app.demo import load_seed, maybe_enter_demo_mode
from app.models import Article, Battlecard, Digest
from tests.conftest import FakeGateway


class DeadGateway(FakeGateway):
    def available(self) -> bool:
        return False


def test_load_seed_inserts_everything(session_factory):
    settings = Settings(_env_file=None)
    n = load_seed(session_factory, settings.demo_seed_path)
    with session_factory() as s:
        assert s.query(Article).count() == n["articles"] >= 3
        assert s.query(Digest).count() >= 1
        assert s.query(Battlecard).count() >= 2
        a = s.get(Article, 1)
        assert a.source_type == "demo" and a.delta_strategic_impact == "medium"


def test_load_seed_idempotent(session_factory):
    settings = Settings(_env_file=None)
    load_seed(session_factory, settings.demo_seed_path)
    again = load_seed(session_factory, settings.demo_seed_path)
    assert again["articles"] == 0  # DB non-empty -> no duplicate load


def test_maybe_enter_demo_mode_matrix(session_factory):
    s_on = Settings(_env_file=None, demo_mode="on")
    s_off = Settings(_env_file=None, demo_mode="off")
    s_auto = Settings(_env_file=None, demo_mode="auto")
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_on) is True
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_off) is False
    assert maybe_enter_demo_mode(session_factory, FakeGateway(), s_auto) is False
    assert maybe_enter_demo_mode(session_factory, DeadGateway(), s_auto) is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_demo.py -v`
Expected: FAIL — ImportError (`load_seed` doesn't exist).

- [ ] **Step 4: Implement demo loader**

Replace `backend/app/demo.py`:
```python
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.models import Article, Battlecard, Digest

log = logging.getLogger("ribbit.demo")


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def load_seed(session_factory, seed_path: Path) -> dict:
    counts = {"articles": 0, "digests": 0, "battlecards": 0}
    if not Path(seed_path).exists():
        log.warning("demo seed missing: %s", seed_path)
        return counts
    data = json.loads(Path(seed_path).read_text())
    with session_factory() as s:
        if s.scalar(select(Article.id).limit(1)):
            return counts  # already populated - never double-load
        for a in data.get("articles", []):
            s.add(Article(id=a["id"], url=a["url"], content_hash=f"demo-{a['id']}",
                          title=a["title"], body_excerpt=a.get("body_excerpt", ""),
                          source_name=a["source_name"], source_type=a["source_type"],
                          published_at=_dt(a.get("published_at")),
                          fetched_at=_dt(a.get("fetched_at")), status=a["status"],
                          relevant=a.get("relevant"), competitors=a.get("competitors"),
                          domain=a.get("domain"), event_type=a.get("event_type"),
                          summary=a.get("summary"), jfrog_impact=a.get("jfrog_impact"),
                          so_what=a.get("so_what"), delta_move=a.get("delta_move"),
                          delta_jfrog_equivalent=a.get("delta_jfrog_equivalent"),
                          delta_strategic_impact=a.get("delta_strategic_impact"),
                          delta_talking_points=a.get("delta_talking_points")))
            counts["articles"] += 1
        for d in data.get("digests", []):
            s.add(Digest(date=d["date"], exec_summary=d["exec_summary"],
                         sections=d["sections"], model_used=d.get("model_used", "demo-seed")))
            counts["digests"] += 1
        for b in data.get("battlecards", []):
            s.add(Battlecard(competitor_slug=b["competitor_slug"],
                             recent_moves=b["recent_moves"]))
            counts["battlecards"] += 1
        s.commit()
    log.info("demo seed loaded: %s", counts)
    return counts


def maybe_enter_demo_mode(session_factory, gateway, settings) -> bool:
    if settings.demo_mode == "off":
        return False
    demo = settings.demo_mode == "on" or not gateway.available()
    if demo:
        load_seed(session_factory, settings.demo_seed_path)
    return demo
```

- [ ] **Step 5: Create the seed-capture script (used in Task 24)**

`scripts/capture_seed.py`:
```python
"""Snapshot the current DB into data/demo/seed.json (run after a real refresh)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, select          # noqa: E402
from sqlalchemy.orm import sessionmaker               # noqa: E402

from app.config import Settings                        # noqa: E402
from app.models import Article, Battlecard, Digest     # noqa: E402

settings = Settings()
engine = create_engine(settings.database_url)
S = sessionmaker(bind=engine)

with S() as s:
    articles = s.scalars(select(Article).where(Article.status == "enriched",
                                               Article.relevant.is_(True))
                         .order_by(Article.id)).all()
    out = {
        "articles": [{
            "id": a.id, "url": a.url, "title": a.title, "body_excerpt": a.body_excerpt[:400],
            "source_name": a.source_name, "source_type": a.source_type,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
            "status": a.status, "relevant": a.relevant, "competitors": a.competitors,
            "domain": a.domain, "event_type": a.event_type, "summary": a.summary,
            "jfrog_impact": a.jfrog_impact, "so_what": a.so_what,
            "delta_move": a.delta_move, "delta_jfrog_equivalent": a.delta_jfrog_equivalent,
            "delta_strategic_impact": a.delta_strategic_impact,
            "delta_talking_points": a.delta_talking_points} for a in articles],
        "digests": [{"date": d.date, "exec_summary": d.exec_summary, "sections": d.sections,
                     "model_used": d.model_used}
                    for d in s.scalars(select(Digest)).all()],
        "battlecards": [{"competitor_slug": b.competitor_slug, "recent_moves": b.recent_moves}
                        for b in s.scalars(select(Battlecard)).all()],
    }

dest = Path(__file__).resolve().parents[1] / "data" / "demo" / "seed.json"
dest.write_text(json.dumps(out, indent=1))
print(f"wrote {dest}: {len(out['articles'])} articles, {len(out['digests'])} digests, "
      f"{len(out['battlecards'])} battlecards")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_demo.py -v && pytest -q`
Expected: 3 passed; full suite green.

- [ ] **Step 7: Manual smoke — keyless boot**

Run:
```bash
cd backend && uvicorn app.main:create_app --factory --port 8000 &
sleep 2 && curl -s localhost:8000/api/meta | python3 -m json.tool && curl -s localhost:8000/api/digest | head -c 400; kill %1
```
Expected: `"demo_mode": true` (no keys in env) and the sample digest JSON.

- [ ] **Step 8: Commit**

```bash
git add backend data scripts && git commit -m "feat(demo): keyless demo mode with bundled seed + capture script"
```

---

### Task 16: Frontend scaffold, API client, layout + status strip

**Files:**
- Create: `frontend/` via Vite template, then `frontend/vite.config.ts`, `frontend/src/index.css`, `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/components/StatusStrip.tsx`, `frontend/src/components/ui.tsx`

- [ ] **Step 1: Scaffold**

```bash
cd /path/to/ribbit
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install @tanstack/react-query react-router-dom recharts
npm install -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @vitest/ui
rm -f src/App.css src/assets/react.svg public/vite.svg
```

- [ ] **Step 2: Config + styles**

`frontend/vite.config.ts` (replace):
```ts
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: "./src/test-setup.ts", globals: true },
});
```

`frontend/src/index.css` (replace entirely):
```css
@import "tailwindcss";

:root { color-scheme: dark; }
body { @apply bg-slate-950 text-slate-100 antialiased; }
```

`frontend/src/test-setup.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 3: Types + API client**

`frontend/src/types.ts`:
```ts
export interface Delta {
  move: string;
  jfrog_equivalent: string;
  strategic_impact: "high" | "medium" | "low";
  talking_points: string[];
}
export interface Article {
  id: number; title: string; url: string; source_name: string; source_type: string;
  published_at: string | null; fetched_at: string | null; competitors: string[];
  domain: string | null; event_type: string | null; summary: string | null;
  jfrog_impact: number | null; so_what: string | null; delta: Delta | null;
}
export interface ArticleRef {
  id: number; title: string; url: string; published_at: string | null; source_name: string;
}
export interface Claim { text: string; article_ids: number[]; kind?: "threat" | "opportunity" }
export interface Digest {
  date: string; exec_summary: string; generated_at: string; model_used: string;
  sections: {
    top_developments: Claim[];
    by_competitor: { competitor: string; highlights: Claim[] }[];
    threats_opportunities: Claim[];
  };
  articles: Record<string, ArticleRef>;
}
export interface Competitor {
  slug: string; name: string; color: string; article_count: number;
  high_impact_count: number; last_activity: string | null;
}
export interface Battlecard {
  slug: string; name: string; color: string;
  base: { strengths: string[]; weaknesses: string[]; how_jfrog_wins: string[] };
  recent_moves: Claim[]; generated_at: string | null; articles: Record<string, ArticleRef>;
}
export interface MatrixCell { level: "full" | "partial" | "addon" | "none"; note: string }
export interface Matrix {
  vendors: string[]; vendor_labels: Record<string, string>;
  rows: { capability: string; values: Record<string, MatrixCell> }[];
}
export interface Meta {
  provider: string; model: string; demo_mode: boolean; refresh_hour: number;
  last_refresh: string | null; competitors: number; version: string;
  refresh_state: { running: boolean; stage: string; errors: string[] };
}
export interface SourceHealth {
  source_name: string; ok: boolean; items_found: number; error: string | null; started_at: string;
}
export interface ArticlePage { items: Article[]; total: number; page: number; page_size: number }
```

`frontend/src/api.ts`:
```ts
async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
export const api = {
  meta: () => get<import("./types").Meta>("/api/meta"),
  digest: (date?: string) =>
    get<import("./types").Digest>(`/api/digest${date ? `?date=${date}` : ""}`),
  digestDates: () => get<string[]>("/api/digest/dates"),
  articles: (params: Record<string, string | number>) =>
    get<import("./types").ArticlePage>(`/api/articles?${new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== 0)
        .map(([k, v]) => [k, String(v)])))}`),
  competitors: () => get<import("./types").Competitor[]>("/api/competitors"),
  battlecard: (slug: string) => get<import("./types").Battlecard>(`/api/competitors/${slug}/battlecard`),
  matrix: () => get<import("./types").Matrix>("/api/matrix"),
  sources: () => get<import("./types").SourceHealth[]>("/api/sources/health"),
  refresh: () => fetch("/api/refresh", { method: "POST" }),
};
```

- [ ] **Step 4: Shared UI atoms**

`frontend/src/components/ui.tsx`:
```tsx
import type { ArticleRef } from "../types";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>{children}</div>;
}

export function ImpactBadge({ value }: { value: number | null }) {
  const v = value ?? 1;
  const color = v >= 4 ? "bg-red-500/20 text-red-300 border-red-500/40"
    : v === 3 ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
    : "bg-slate-600/20 text-slate-300 border-slate-600/40";
  return <span className={`rounded-md border px-1.5 py-0.5 text-xs font-semibold ${color}`}>impact {v}</span>;
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="rounded-md bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">{children}</span>;
}

export function CitationChips({ ids, articles }: { ids: number[]; articles: Record<string, ArticleRef> }) {
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {ids.map((id) => {
        const ref = articles[String(id)];
        if (!ref) return null;
        const date = ref.published_at ? new Date(ref.published_at).toISOString().slice(0, 10) : "";
        return (
          <a key={id} href={ref.url} target="_blank" rel="noreferrer" title={`${ref.title} — ${ref.source_name}`}
             className="rounded bg-emerald-900/50 px-1 text-xs text-emerald-300 hover:bg-emerald-800">
            [{id}]{date && ` ${date}`}
          </a>
        );
      })}
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="p-8 text-center text-sm text-slate-400">{label}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
    {String(error)}
  </div>;
}
```

- [ ] **Step 5: Status strip + app shell**

`frontend/src/components/StatusStrip.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export default function StatusStrip() {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, refetchInterval: 5000 });
  const refresh = useMutation({
    mutationFn: api.refresh,
    onSettled: () => qc.invalidateQueries(),
  });
  if (!meta.data) return null;
  const m = meta.data;
  const running = m.refresh_state.running;
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-900 px-4 py-2 text-xs text-slate-400">
      <span className="font-bold text-emerald-400">🐸 Ribbit</span>
      {m.demo_mode && (
        <span className="rounded bg-amber-500/20 px-2 py-0.5 font-semibold text-amber-300">
          DEMO MODE — bundled data, no live LLM
        </span>
      )}
      <span>LLM: {m.demo_mode ? "none" : `${m.provider}/${m.model}`}</span>
      <span>last refresh: {m.last_refresh ? new Date(m.last_refresh).toLocaleString() : "never"}</span>
      {running && <span className="text-sky-300">refreshing: {m.refresh_state.stage}…</span>}
      {m.refresh_state.errors.length > 0 && (
        <span className="text-red-400" title={m.refresh_state.errors.join("\n")}>
          {m.refresh_state.errors.length} source error(s)
        </span>
      )}
      <button
        onClick={() => refresh.mutate()}
        disabled={m.demo_mode || running}
        title={m.demo_mode ? "Disabled in demo mode" : "Fetch + analyze now"}
        className="ml-auto rounded-md bg-emerald-600 px-3 py-1 font-semibold text-white disabled:opacity-40">
        {running ? "Running…" : "Refresh now"}
      </button>
    </div>
  );
}
```

`frontend/src/App.tsx` (replace):
```tsx
import { NavLink, Outlet } from "react-router-dom";
import StatusStrip from "./components/StatusStrip";

const tabs = [
  { to: "/", label: "Today" },
  { to: "/feed", label: "Feed" },
  { to: "/competitors", label: "Competitors" },
  { to: "/compare", label: "Compare" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <StatusStrip />
      <nav className="flex gap-1 border-b border-slate-800 bg-slate-900/60 px-4">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === "/"}
            className={({ isActive }) =>
              `px-4 py-2 text-sm font-medium ${isActive
                ? "border-b-2 border-emerald-400 text-emerald-300"
                : "text-slate-400 hover:text-slate-200"}`}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <main className="mx-auto max-w-6xl p-4"><Outlet /></main>
    </div>
  );
}
```

`frontend/src/main.tsx` (replace):
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import "./index.css";
import Compare from "./pages/Compare";
import CompetitorDetail from "./pages/CompetitorDetail";
import Competitors from "./pages/Competitors";
import Feed from "./pages/Feed";
import Today from "./pages/Today";

const router = createBrowserRouter([
  { path: "/", element: <App />, children: [
    { index: true, element: <Today /> },
    { path: "feed", element: <Feed /> },
    { path: "competitors", element: <Competitors /> },
    { path: "competitors/:slug", element: <CompetitorDetail /> },
    { path: "compare", element: <Compare /> },
  ]},
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

Create empty placeholder pages so it compiles (filled in Tasks 17-20) — each of `frontend/src/pages/{Today,Feed,Competitors,CompetitorDetail,Compare}.tsx`:
```tsx
export default function Page() { return <div className="text-slate-400">Coming in a later task…</div>; }
```
(Rename the function per file: Today, Feed, Competitors, CompetitorDetail, Compare.)

Also set `<title>Ribbit — Competitive Intelligence</title>` in `frontend/index.html`.

- [ ] **Step 6: Verify**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors, build succeeds.
Optional live check: `npm run dev` with backend running — tabs render, status strip shows DEMO MODE.

- [ ] **Step 7: Commit**

```bash
git add frontend && git commit -m "feat(frontend): scaffold, typed API client, shell with status strip"
```

---

### Task 17: Today page (digest)

**Files:**
- Modify: `frontend/src/pages/Today.tsx`

- [ ] **Step 1: Implement**

`frontend/src/pages/Today.tsx` (replace placeholder):
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Card, CitationChips, ErrorBox, Spinner } from "../components/ui";

export default function Today() {
  const [date, setDate] = useState<string>("");
  const dates = useQuery({ queryKey: ["digestDates"], queryFn: api.digestDates });
  const digest = useQuery({
    queryKey: ["digest", date],
    queryFn: () => api.digest(date || undefined),
    retry: false,
  });

  if (digest.isLoading) return <Spinner label="Loading digest…" />;
  if (digest.isError) return <ErrorBox error="No digest yet — run a refresh (or check demo mode)." />;
  const d = digest.data!;
  const s = d.sections;
  const kpis = [
    { label: "Top developments", value: s.top_developments.length },
    { label: "Competitors active", value: s.by_competitor.length },
    { label: "Threats", value: s.threats_opportunities.filter(t => t.kind === "threat").length },
    { label: "Opportunities", value: s.threats_opportunities.filter(t => t.kind === "opportunity").length },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Daily digest — {d.date}</h1>
        <select value={date} onChange={(e) => setDate(e.target.value)}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm">
          <option value="">latest</option>
          {(dates.data ?? []).map((dt) => <option key={dt} value={dt}>{dt}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label} className="text-center">
            <div className="text-2xl font-bold text-emerald-300">{k.value}</div>
            <div className="text-xs text-slate-400">{k.label}</div>
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="mb-1 text-sm font-semibold text-slate-300">
          Executive summary
          <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-normal text-slate-400"
                title="Synthesis of the cited claims below. Unlike those claims, this paragraph carries no per-source citations.">
            AI SYNTHESIS
          </span>
        </h2>
        <p className="text-slate-100">{d.exec_summary}</p>
        <p className="mt-2 text-xs text-slate-500">generated {new Date(d.generated_at).toLocaleString()} · {d.model_used}</p>
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-300">Top developments</h2>
        <ul className="space-y-2">
          {s.top_developments.map((c, i) => (
            <li key={i} className="text-sm">• {c.text}<CitationChips ids={c.article_ids} articles={d.articles} /></li>
          ))}
          {s.top_developments.length === 0 && <li className="text-sm text-slate-500">Quiet day.</li>}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-300">By competitor</h2>
          {s.by_competitor.map((b) => (
            <div key={b.competitor} className="mb-2">
              <div className="text-sm font-semibold capitalize text-slate-200">{b.competitor}</div>
              <ul>{b.highlights.map((h, i) => (
                <li key={i} className="text-sm text-slate-300">– {h.text}
                  <CitationChips ids={h.article_ids} articles={d.articles} /></li>))}
              </ul>
            </div>
          ))}
        </Card>
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-300">Threats & opportunities</h2>
          <ul className="space-y-2">
            {s.threats_opportunities.map((t, i) => (
              <li key={i} className="text-sm">
                <span className={`mr-1 rounded px-1.5 py-0.5 text-xs font-bold ${
                  t.kind === "threat" ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-300"}`}>
                  {t.kind}
                </span>
                {t.text}<CitationChips ids={t.article_ids} articles={d.articles} />
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify + commit**

Run: `npx tsc --noEmit && npm run build` — clean. Visual check against demo data.
```bash
git add frontend && git commit -m "feat(frontend): Today digest page with cited claims"
```

---

### Task 18: Feed page

**Files:**
- Modify: `frontend/src/pages/Feed.tsx`

- [ ] **Step 1: Implement**

`frontend/src/pages/Feed.tsx` (replace placeholder):
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Card, ErrorBox, ImpactBadge, Spinner, Tag } from "../components/ui";
import type { Article } from "../types";

const DOMAINS = ["", "artifact_management", "container_registry", "devsecops_scanning", "cicd", "sbom_supply_chain", "other"];
const EVENTS = ["", "product_launch", "feature_update", "security_advisory", "pricing_change", "funding_ma", "partnership", "other"];
const COMPETITORS = ["", "sonatype", "gitlab", "github", "docker", "snyk"];

function DeltaPanel({ a }: { a: Article }) {
  if (!a.delta) return null;
  return (
    <div className="mt-2 rounded-lg border border-emerald-900 bg-emerald-950/40 p-2 text-xs">
      <div className="font-bold text-emerald-300">JFrog Delta — {a.delta.strategic_impact.toUpperCase()}</div>
      <div className="mt-1 text-slate-300"><b>Move:</b> {a.delta.move}</div>
      <div className="text-slate-300"><b>JFrog equivalent:</b> {a.delta.jfrog_equivalent}</div>
      {a.delta.talking_points.length > 0 && (
        <ul className="mt-1 list-inside list-disc text-slate-400">
          {a.delta.talking_points.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function Feed() {
  const [f, setF] = useState({ competitor: "", domain: "", event_type: "", min_impact: 0, q: "", page: 1 });
  const feed = useQuery({
    queryKey: ["articles", f],
    queryFn: () => api.articles({ ...f }),
    placeholderData: (prev) => prev,
  });
  const sel = "rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select className={sel} value={f.competitor} onChange={(e) => setF({ ...f, competitor: e.target.value, page: 1 })}>
          {COMPETITORS.map((c) => <option key={c} value={c}>{c || "all competitors"}</option>)}
        </select>
        <select className={sel} value={f.domain} onChange={(e) => setF({ ...f, domain: e.target.value, page: 1 })}>
          {DOMAINS.map((d) => <option key={d} value={d}>{d || "all domains"}</option>)}
        </select>
        <select className={sel} value={f.event_type} onChange={(e) => setF({ ...f, event_type: e.target.value, page: 1 })}>
          {EVENTS.map((ev) => <option key={ev} value={ev}>{ev || "all events"}</option>)}
        </select>
        <select className={sel} value={f.min_impact} onChange={(e) => setF({ ...f, min_impact: +e.target.value, page: 1 })}>
          <option value={0}>any impact</option><option value={3}>impact ≥ 3</option><option value={4}>impact ≥ 4</option>
        </select>
        <input className={`${sel} flex-1`} placeholder="search…" value={f.q}
               onChange={(e) => setF({ ...f, q: e.target.value, page: 1 })} />
      </div>

      {feed.isLoading && <Spinner label="Loading feed…" />}
      {feed.isError && <ErrorBox error={feed.error} />}
      {feed.data && (
        <>
          <div className="text-xs text-slate-500">{feed.data.total} items</div>
          {feed.data.items.map((a) => (
            <Card key={a.id}>
              <div className="flex flex-wrap items-center gap-2">
                <ImpactBadge value={a.jfrog_impact} />
                {a.competitors.map((c) => <Tag key={c}>{c}</Tag>)}
                {a.domain && <Tag>{a.domain}</Tag>}
                {a.event_type && <Tag>{a.event_type}</Tag>}
                <span className="ml-auto text-xs text-slate-500">
                  {a.published_at ? new Date(a.published_at).toLocaleDateString() : ""} · {a.source_name}
                </span>
              </div>
              <a href={a.url} target="_blank" rel="noreferrer"
                 className="mt-1 block font-semibold text-slate-100 hover:text-emerald-300">{a.title}</a>
              {a.summary && <p className="mt-1 text-sm text-slate-300">{a.summary}</p>}
              {a.so_what && <p className="mt-1 text-sm italic text-amber-200/90">So what: {a.so_what}</p>}
              <DeltaPanel a={a} />
            </Card>
          ))}
          <div className="flex items-center gap-2 text-sm">
            <button disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })}
                    className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40">prev</button>
            <span>page {f.page}</span>
            <button disabled={f.page * feed.data.page_size >= feed.data.total}
                    onClick={() => setF({ ...f, page: f.page + 1 })}
                    className="rounded bg-slate-800 px-3 py-1 disabled:opacity-40">next</button>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify + commit**

Run: `npx tsc --noEmit && npm run build` — clean.
```bash
git add frontend && git commit -m "feat(frontend): filterable feed with so-what and delta panels"
```

---

### Task 19: Competitors + battlecard pages

**Files:**
- Modify: `frontend/src/pages/Competitors.tsx`, `frontend/src/pages/CompetitorDetail.tsx`

- [ ] **Step 1: Implement list page**

`frontend/src/pages/Competitors.tsx` (replace placeholder):
```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card, Spinner } from "../components/ui";

export default function Competitors() {
  const q = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  if (!q.data) return <Spinner />;
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {q.data.map((c) => (
        <Link key={c.slug} to={`/competitors/${c.slug}`}>
          <Card className="transition hover:border-emerald-700">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ background: c.color }} />
              <span className="text-lg font-bold">{c.name}</span>
            </div>
            <div className="mt-2 flex gap-4 text-sm text-slate-400">
              <span>{c.article_count} items (14d)</span>
              <span className={c.high_impact_count ? "text-red-300" : ""}>{c.high_impact_count} high-impact</span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              last activity: {c.last_activity ? new Date(c.last_activity).toLocaleDateString() : "—"}
            </div>
          </Card>
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Implement battlecard page**

`frontend/src/pages/CompetitorDetail.tsx` (replace placeholder):
```tsx
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Card, CitationChips, ErrorBox, Spinner } from "../components/ui";

function CuratedList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <Card>
      <h3 className={`mb-2 text-sm font-bold ${tone}`}>{title}
        <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-normal text-slate-400">CURATED</span>
      </h3>
      <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
        {items.map((s, i) => <li key={i}>{s}</li>)}
      </ul>
    </Card>
  );
}

export default function CompetitorDetail() {
  const { slug = "" } = useParams();
  const q = useQuery({ queryKey: ["battlecard", slug], queryFn: () => api.battlecard(slug), retry: false });
  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorBox error={q.error} />;
  const b = q.data!;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 rounded-full" style={{ background: b.color }} />
        <h1 className="text-xl font-bold">{b.name} battlecard</h1>
        <Link to="/competitors" className="ml-auto text-sm text-slate-400 hover:text-slate-200">← all competitors</Link>
      </div>

      <Card className="border-emerald-900">
        <h3 className="mb-2 text-sm font-bold text-emerald-300">Recent moves & signals
          <span className="ml-2 rounded bg-emerald-900/60 px-1.5 py-0.5 text-[10px] font-normal text-emerald-300">
            GENERATED · CITED
          </span>
        </h3>
        {b.recent_moves.length === 0 && <p className="text-sm text-slate-500">No recent enriched items yet — run a refresh.</p>}
        <ul className="space-y-2 text-sm text-slate-200">
          {b.recent_moves.map((m, i) => (
            <li key={i}>• {m.text}<CitationChips ids={m.article_ids} articles={b.articles} /></li>
          ))}
        </ul>
        {b.generated_at && <p className="mt-2 text-xs text-slate-500">updated {new Date(b.generated_at).toLocaleString()}</p>}
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <CuratedList title="Strengths" items={b.base.strengths} tone="text-sky-300" />
        <CuratedList title="Weaknesses" items={b.base.weaknesses} tone="text-amber-300" />
        <CuratedList title="How JFrog wins" items={b.base.how_jfrog_wins} tone="text-emerald-300" />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify + commit**

Run: `npx tsc --noEmit && npm run build` — clean.
```bash
git add frontend && git commit -m "feat(frontend): competitor cards + curated/generated battlecard view"
```

---

### Task 20: Compare page (matrix + radar)

**Files:**
- Modify: `frontend/src/pages/Compare.tsx`

- [ ] **Step 1: Implement**

`frontend/src/pages/Compare.tsx` (replace placeholder):
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Legend } from "recharts";
import { api } from "../api";
import { Card, Spinner } from "../components/ui";
import type { MatrixCell } from "../types";

const SCORE: Record<MatrixCell["level"], number> = { full: 3, partial: 2, addon: 1, none: 0 };
const GLYPH: Record<MatrixCell["level"], string> = { full: "●", partial: "◐", addon: "◍", none: "○" };
const COLOR: Record<string, string> = {
  jfrog: "#41bf47", sonatype: "#79b62f", gitlab: "#fc6d26",
  github: "#8b5cf6", docker: "#2496ed", snyk: "#b45ab8",
};

export default function Compare() {
  const q = useQuery({ queryKey: ["matrix"], queryFn: api.matrix });
  const [selected, setSelected] = useState<string[]>(["jfrog", "sonatype", "gitlab"]);
  if (!q.data) return <Spinner />;
  const m = q.data;
  const toggle = (v: string) =>
    setSelected((s) => (s.includes(v) ? s.filter((x) => x !== v && x !== "jfrog" ? true : x !== v) : [...s, v]));
  const radarData = m.rows.map((r) => ({
    capability: r.capability.replace(" / ", "/"),
    ...Object.fromEntries(selected.map((v) => [v, SCORE[r.values[v].level]])),
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {m.vendors.map((v) => (
          <button key={v} onClick={() => v !== "jfrog" && toggle(v)}
                  className={`rounded-full border px-3 py-1 text-sm ${selected.includes(v)
                    ? "border-emerald-600 bg-emerald-900/40 text-emerald-200"
                    : "border-slate-700 text-slate-400"} ${v === "jfrog" ? "cursor-default font-bold" : ""}`}>
            {m.vendor_labels[v] ?? v}
          </button>
        ))}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400">
                <th className="p-2">Capability</th>
                {selected.map((v) => <th key={v} className="p-2">{m.vendor_labels[v] ?? v}</th>)}
              </tr>
            </thead>
            <tbody>
              {m.rows.map((r) => (
                <tr key={r.capability} className="border-t border-slate-800">
                  <td className="p-2 font-medium text-slate-200">{r.capability}</td>
                  {selected.map((v) => {
                    const cell = r.values[v];
                    return (
                      <td key={v} className="p-2" title={cell.note}>
                        <span className={cell.level === "full" ? "text-emerald-300"
                          : cell.level === "partial" ? "text-amber-300"
                          : cell.level === "addon" ? "text-sky-300" : "text-slate-600"}>
                          {GLYPH[cell.level]} {cell.level}
                        </span>
                        {cell.note && <span className="ml-1 text-xs text-slate-500">({cell.note})</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">Curated matrix (config/feature_matrix.yaml) — facts are human-reviewed, not LLM-generated.</p>
      </Card>

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-300">Capability radar</h3>
        <div className="h-96">
          <ResponsiveContainer>
            <RadarChart data={radarData} outerRadius="70%">
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis dataKey="capability" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              {selected.map((v) => (
                <Radar key={v} name={m.vendor_labels[v] ?? v} dataKey={v}
                       stroke={COLOR[v] ?? "#ccc"} fill={COLOR[v] ?? "#ccc"} fillOpacity={0.15} />
              ))}
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
```

Note: fix the `toggle` helper if it reads awkwardly — intent: jfrog is always selected; others toggle:
```tsx
const toggle = (v: string) =>
  setSelected((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
```
(jfrog is guarded at the call site with `v !== "jfrog" && toggle(v)` — keep that version.)

- [ ] **Step 2: Verify + commit**

Run: `npx tsc --noEmit && npm run build` — clean.
```bash
git add frontend && git commit -m "feat(frontend): comparison matrix + capability radar"
```

---

### Task 21: Frontend component tests

**Files:**
- Test: `frontend/src/components/ui.test.tsx`
- Modify: `frontend/package.json` (scripts)

- [ ] **Step 1: Write tests**

`frontend/src/components/ui.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationChips, ImpactBadge } from "./ui";

describe("CitationChips", () => {
  const articles = {
    "7": { id: 7, title: "Snyk pricing", url: "https://x/7", published_at: "2026-08-02T00:00:00Z", source_name: "Blog" },
  };
  it("renders links only for resolvable ids", () => {
    render(<CitationChips ids={[7, 999]} articles={articles} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://x/7");
    expect(link.textContent).toContain("[7]");
    expect(link.textContent).toContain("2026-08-02");   // timestamped citation
    expect(screen.queryByText("[999]")).toBeNull();     // hallucinated id renders nothing
  });
});

describe("ImpactBadge", () => {
  it("colors high impact red-ish and shows value", () => {
    render(<ImpactBadge value={5} />);
    expect(screen.getByText("impact 5").className).toContain("red");
  });
});
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Run tests**

Run: `cd frontend && npm test`
Expected: 2 test files? No — 1 file, 2 tests: **2 passed**.

- [ ] **Step 3: Commit**

```bash
git add frontend && git commit -m "test(frontend): citation chip + impact badge component tests"
```

---

### Task 22: Docker packaging

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `docker-compose.yml`, `.env.example`, `.dockerignore`

- [ ] **Step 1: Create files**

`backend/Dockerfile` (build context = repo root):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY config ./config
COPY data/demo ./data/demo
ENV DATABASE_URL=sqlite:////data/ribbit.db \
    CONFIG_DIR=/app/config \
    DEMO_SEED_PATH=/app/data/demo/seed.json
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

**Required tweak:** `Settings.config_dir` / `demo_seed_path` / `database_url` must respect env vars — they already do (pydantic-settings maps `CONFIG_DIR`, `DEMO_SEED_PATH`, `DATABASE_URL` automatically since the fields exist). Verify with the compose smoke test below.

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
    }
    location / {
        try_files $uri /index.html;
    }
}
```

`frontend/Dockerfile` (build context = frontend/):
```dockerfile
FROM node:20-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
```

`docker-compose.yml`:
```yaml
services:
  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file:
      - path: .env
        required: false
    environment:
      - DATABASE_URL=sqlite:////data/ribbit.db
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
    volumes:
      - ribbit-data:/data
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
  web:
    build:
      context: frontend
    ports:
      - "3000:80"
    depends_on:
      - api
volumes:
  ribbit-data:
```

`.env.example`:
```
# LLM provider: anthropic | openai | gemini | ollama  (leave keys empty for demo mode)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
LLM_FALLBACK_PROVIDER=
# Optional broader news search
TAVILY_API_KEY=
# Daily refresh hour (local server time)
REFRESH_HOUR=07
# auto | on | off
DEMO_MODE=auto
```

`.dockerignore`:
```
**/.venv
**/node_modules
**/__pycache__
**/.pytest_cache
frontend/dist
data/*.db
.git
```

- [ ] **Step 2: Smoke test**

Run:
```bash
docker compose up --build -d
sleep 5
curl -s localhost:8000/api/meta | python3 -m json.tool | head -20
curl -s localhost:3000/api/meta | python3 -m json.tool | head -5   # via nginx proxy
curl -s -o /dev/null -w "%{http_code}\n" localhost:3000            # SPA serves: 200
docker compose down
```
Expected: `"demo_mode": true` (no .env), proxy works, SPA 200.

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf docker-compose.yml .env.example .dockerignore
git commit -m "feat(deploy): docker compose packaging (nginx SPA + api, keyless demo works)"
```

---

### Task 23: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`, `backend/ruff.toml`

- [ ] **Step 1: Create files**

`backend/ruff.toml`:
```toml
line-length = 100
target-version = "py312"
[lint]
select = ["E", "F", "I", "UP"]
```

`.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push: {branches: [main]}
  pull_request:
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -r backend/requirements-dev.txt
      - run: cd backend && ruff check .
      - run: cd backend && pytest -q
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json}
      - run: cd frontend && npm ci
      - run: cd frontend && npx tsc --noEmit
      - run: cd frontend && npm test
      - run: cd frontend && npm run build
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
```

- [ ] **Step 2: Verify locally**

Run: `cd backend && ruff check . && pytest -q && cd ../frontend && npm test && npm run build`
Expected: everything green (fix any ruff nits it finds — import order etc.).

- [ ] **Step 3: Commit**

```bash
git add .github backend/ruff.toml && git commit -m "ci: lint + tests + docker build on push/PR"
```

---

### Task 24: Real data capture, screenshots, README, docs sync

This is the delivery task — run the system for real once, snapshot it, document it.

**Files:**
- Modify: `data/demo/seed.json` (replaced by real capture), `README.md` (create), `docs/screenshots/*.png` (create), `INSIGHTS.md`, `ARCHITECTURE.md`, `DECISIONS.md` (sync if anything drifted)

- [ ] **Step 1: One real refresh (requires the user's Anthropic key)**

```bash
cp .env.example .env   # then put the real ANTHROPIC_API_KEY into .env (user does this - never commit .env)
cd backend && source .venv/bin/activate
uvicorn app.main:create_app --factory --port 8000 &
sleep 2
curl -s -X POST localhost:8000/api/refresh
watch -n 2 'curl -s localhost:8000/api/refresh/status'   # until stage=done (Ctrl+C)
curl -s localhost:8000/api/sources/health | python3 -m json.tool
```
Expected: majority of sources `ok: true` with items. **If a feed URL 404s** (they drift), fix the URL in `config/competitors.yaml` / `config/industry_feeds.yaml`, rerun refresh, and log the fix in INSIGHTS.md. Then:
```bash
curl -s localhost:8000/api/digest | python3 -m json.tool | head -40   # sanity-read the digest
kill %1
```

- [ ] **Step 2: Capture the seed from real data**

```bash
python3 scripts/capture_seed.py
git diff --stat data/demo/seed.json   # should show a real-sized dataset now
```
Review `data/demo/seed.json` briefly: real titles/URLs, citations resolve. Commit:
```bash
git add data/demo/seed.json && git commit -m "data: capture real demo seed from live refresh"
```

- [ ] **Step 3: Keyless end-to-end verification (the reviewer experience)**

```bash
mv .env /tmp/ribbit.env.backup   # simulate reviewer with no keys
docker compose up --build -d && sleep 5
```
Open http://localhost:3000 — Today shows the real digest with DEMO badge; Feed filters work; battlecards cite real articles; Compare renders. Restore: `mv /tmp/ribbit.env.backup .env`.

- [ ] **Step 4: Screenshots**

With the app up, capture (any tool; keep exact filenames):
- `docs/screenshots/today.png` — Today tab
- `docs/screenshots/feed.png` — Feed with a Delta panel visible
- `docs/screenshots/compare.png` — matrix + radar
- `docs/screenshots/battlecard.png` — one battlecard

- [ ] **Step 5: Write README.md**

```markdown
# 🐸 Ribbit — Competitive Intelligence for JFrog

Ribbit keeps JFrog's Competitive Intelligence team on top of a daily-shifting landscape:
it ingests domain-curated news about Sonatype, GitLab, GitHub, Docker and Snyk every day,
uses an LLM to filter noise and structure each item (domain, event type, impact-for-JFrog,
the one-line "so what"), and publishes a cited daily digest, per-competitor battlecards,
and a JFrog-vs-competitor comparison — in one dashboard.

![Today](docs/screenshots/today.png)

## Quick start (zero keys needed)

    docker compose up --build

Open **http://localhost:3000**. With no API keys configured, Ribbit boots in **demo mode**
with a bundled dataset captured from a real pipeline run — every tab is populated.

## Live mode (real daily intelligence)

    cp .env.example .env    # add ANTHROPIC_API_KEY (or switch LLM_PROVIDER; see below)
    docker compose up --build

- Click **Refresh now** (or wait for the daily 07:00 run) to fetch + analyze fresh news.
- Provider-agnostic by design: `LLM_PROVIDER=anthropic|openai|gemini|ollama` — local Ollama
  keeps sensitive competitive data fully in-house.
- Optional: `TAVILY_API_KEY` widens coverage with a news-search API.

## How it works

Fetch (RSS / Hacker News / Reddit / Tavily, per-source isolation) → dedupe (canonical URL +
content hash) → LLM enrichment (strict relevance gate, domain × event taxonomy, impact 1-5)
→ Delta analysis for high-impact moves (grounded in a curated JFrog capability sheet) →
cited daily digest → cited battlecard refresh. Full diagrams: [ARCHITECTURE.md](ARCHITECTURE.md).

**Anti-hallucination is structural:** every generated claim must carry `article_ids` that
resolve to ingested sources (schema-enforced, invalid claims dropped); JFrog capabilities
come only from a human-curated sheet; the comparison matrix is config, not generation.
Decision log with rationale for every choice: [DECISIONS.md](DECISIONS.md).

## Built now vs. future roadmap

**Demonstrated now:** daily scheduled pipeline, 5 competitors × ~15 sources, GenAI
enrichment + delta + digest + battlecards with enforced citations, comparison matrix +
radar, keyless demo mode, tests + CI, one-command deploy.

**With more time/resources:** Postgres + pgvector and semantic retrieval at corpus scale;
queue/orchestrator (Airflow) for fan-out; Slack/email digest delivery; human-in-the-loop
curation UI; LLM-output eval harness (golden set, precision tracking); pricing-page and
docs diff-watchers; win/loss and review-site ingestion; autonomous deep-research agents.

## Challenges & pitfalls we hit

See [INSIGHTS.md](INSIGHTS.md) — the honest log (feed drift, noise control, citation
enforcement trade-offs, YAGNI cuts like dropping the vector DB).

## Development

    cd backend && python3.12 -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt && pytest -q       # backend tests
    uvicorn app.main:create_app --factory --reload         # api on :8000
    cd frontend && npm install && npm run dev              # ui on :5173 (proxies /api)

CI runs ruff + pytest + tsc + vitest + docker build on every push.
```

Adjust the screenshot filename(s) if you captured different views. Keep claims accurate to what actually works.

- [ ] **Step 6: Sync the living docs**

- `INSIGHTS.md`: add an implementation-phase section — at minimum: which feeds drifted/died and the fix; anything surprising about LLM output quality/cost; what the citation enforcement actually caught during the real run (check logs for dropped claims).
- `ARCHITECTURE.md`: confirm diagrams still match reality (rename anything that drifted).
- `DECISIONS.md`: append ADRs for any deviation made during implementation.

- [ ] **Step 7: Final commit**

```bash
git add README.md docs INSIGHTS.md ARCHITECTURE.md DECISIONS.md
git commit -m "docs: README, screenshots, real-run insights"
```

---

### Task 25 (STRETCH — only if a day remains): Analyst chat

**Files:**
- Create: `backend/app/retrieval/__init__.py`, `backend/app/retrieval/search.py`, `backend/app/api/routes_chat.py`, `frontend/src/pages/Chat.tsx`
- Modify: `backend/app/main.py` (include router), `frontend/src/main.tsx` + `frontend/src/App.tsx` (add tab)
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chat.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.schemas import ChatAnswer
from app.main import create_app
from app.retrieval.search import search_articles
from tests.conftest import FakeGateway, make_article


def test_fts_search_ranks_matches(session):
    make_article(session, url="https://c.example/1", title="Snyk pricing shakeup",
                 status="enriched", relevant=True, summary="Snyk changed enterprise pricing")
    make_article(session, url="https://c.example/2", title="GitLab registry news",
                 status="enriched", relevant=True, summary="registry cleanup")
    hits = search_articles(session, "snyk pricing", k=5)
    assert hits and hits[0].title == "Snyk pricing shakeup"
    assert search_articles(session, "quantum llamas", k=5) == []


@pytest.fixture()
def client(tmp_path, session_factory):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/chat.db",
                        demo_mode="off", enable_scheduler=False)
    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.gateway = FakeGateway([ChatAnswer(answer="Snyk changed pricing.", citation_ids=[1])])
    with TestClient(app) as c:
        yield c


def test_chat_answers_with_citations(client, session):
    a = make_article(session, url="https://c.example/3", title="Snyk pricing shakeup",
                     status="enriched", relevant=True, summary="Snyk changed pricing")
    r = client.post("/api/chat", json={"question": "What did Snyk do to pricing?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] and isinstance(body["citations"], list)


def test_chat_no_results_short_circuits(client):
    r = client.post("/api/chat", json={"question": "zebra zeppelin xylophone"})
    assert r.status_code == 200
    assert "couldn't find" in r.json()["answer"].lower()
```

- [ ] **Step 2: Run to verify failure, then implement**

Run: `pytest tests/test_chat.py -v` → ModuleNotFoundError.

`backend/app/retrieval/__init__.py`: empty file.

`backend/app/retrieval/search.py`:
```python
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Article


def _fts_query(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", q)
    return " OR ".join(words) if words else '""'


def search_articles(session: Session, query: str, k: int = 8) -> list[Article]:
    rows = session.execute(
        text("SELECT rowid FROM articles_fts WHERE articles_fts MATCH :q "
             "ORDER BY bm25(articles_fts) LIMIT :k"),
        {"q": _fts_query(query), "k": k}).fetchall()
    ids = [r[0] for r in rows]
    if not ids:
        return []
    arts = {a.id: a for a in session.scalars(select(Article).where(Article.id.in_(ids)))}
    return [arts[i] for i in ids if i in arts and arts[i].status == "enriched"]
```

`backend/app/api/routes_chat.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_gateway, get_session_factory
from app.llm.prompts import CHAT_SYSTEM
from app.llm.schemas import ChatAnswer
from app.retrieval.search import search_articles

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
def chat(req: ChatRequest, sf=Depends(get_session_factory), gateway=Depends(get_gateway)):
    if not gateway.available():
        raise HTTPException(503, "No LLM provider available - chat needs one (see README)")
    with sf() as session:
        hits = search_articles(session, req.question, k=8)
        if not hits:
            return {"answer": "I couldn't find anything about that in the ingested news corpus.",
                    "citations": []}
        blob = "\n".join(f"[{a.id}] {a.title} — {a.summary or a.body_excerpt[:200]}" for a in hits)
        out: ChatAnswer | None = gateway.complete_json(
            CHAT_SYSTEM.format(articles=blob), req.question, ChatAnswer)
        if out is None:
            raise HTTPException(502, "LLM failed to answer")
        valid = {a.id: a for a in hits}
        citations = [{"id": a.id, "title": a.title, "url": a.url,
                      "published_at": a.published_at.isoformat() if a.published_at else None}
                     for a in (valid[i] for i in out.citation_ids if i in valid)]
        return {"answer": out.answer, "citations": citations}
```

Wire in `backend/app/main.py`: add `from app.api.routes_chat import router as chat_router` and `app.include_router(chat_router)`.

`frontend/src/pages/Chat.tsx`:
```tsx
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Card } from "../components/ui";

interface Turn { q: string; a?: string; cites?: { id: number; title: string; url: string }[]; err?: string }

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const ask = useMutation({
    mutationFn: async (question: string) => {
      const r = await fetch("/api/chat", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
      if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
      return r.json();
    },
    onSuccess: (data, question) =>
      setTurns((t) => t.map((x) => x.q === question && !x.a && !x.err
        ? { ...x, a: data.answer, cites: data.citations } : x)),
    onError: (e, question) =>
      setTurns((t) => t.map((x) => x.q === question && !x.a && !x.err
        ? { ...x, err: String(e) } : x)),
  });
  const submit = () => {
    if (!q.trim()) return;
    setTurns((t) => [...t, { q }]);
    ask.mutate(q);
    setQ("");
  };
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-400">Answers come only from the ingested news corpus, with citations.</p>
      {turns.map((t, i) => (
        <Card key={i}>
          <div className="text-sm font-semibold text-sky-300">You: {t.q}</div>
          {t.err && <div className="mt-1 text-sm text-red-300">{t.err}</div>}
          {!t.a && !t.err && <div className="mt-1 text-sm text-slate-500">thinking…</div>}
          {t.a && <div className="mt-1 text-sm text-slate-200">{t.a}</div>}
          {t.cites && t.cites.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {t.cites.map((c) => (
                <a key={c.id} href={c.url} target="_blank" rel="noreferrer"
                   className="rounded bg-emerald-900/50 px-1.5 py-0.5 text-xs text-emerald-300"
                   title={c.title}>[{c.id}] {c.title.slice(0, 40)}…</a>
              ))}
            </div>
          )}
        </Card>
      ))}
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && submit()}
               placeholder="e.g. What has Sonatype shipped recently?"
               className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm" />
        <button onClick={submit} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold">Ask</button>
      </div>
    </div>
  );
}
```

Add the route in `frontend/src/main.tsx` children: `{ path: "chat", element: <Chat /> }` (+import), and the tab in `frontend/src/App.tsx`: `{ to: "/chat", label: "Chat" }`.

- [ ] **Step 3: Verify + commit**

Run: `pytest tests/test_chat.py -v` (3 passed) and full suites + builds.
```bash
git add backend frontend && git commit -m "feat(chat): FTS5-retrieval analyst chat with citations (stretch)"
```
Update DECISIONS.md ADR-006 status note ("stretch shipped") and INSIGHTS.md.

---

## Execution notes

- **Order matters** through Task 16; Tasks 17-20 are independent of each other; Task 21+ close out. Task 25 only if time remains after Task 24 — Stage 2 of the assignment needs its days too.
- **Full suite check between tasks:** `cd backend && pytest -q` and `cd frontend && npx tsc --noEmit` are the cheap regression gates.
- **The user must supply their Anthropic key at Task 24 Step 1** (never committed).
- Living docs (DECISIONS / ARCHITECTURE / INSIGHTS) are updated inline with the work, not at the end.

## Plan self-review (done at authoring time)

- **Spec coverage:** goals/architecture (T1-T16), config shapes (T2), data model+FTS (T3), pipeline stages (T4, T8-T12), gateway+prompts (T6), API surface (T13-T14 + T25 chat), 5 UI tabs (T16-T20 + T25), demo mode (T15, T22), error handling (T6/T12 fallbacks + isolation tests), testing+CI (throughout + T23), README now-vs-future + challenges (T24), success criteria (T22 smoke, T24 keyless E2E). Non-goals stay out.
- **Placeholders:** none — every step carries real code/commands. External feed URLs are best-known-good with an explicit runtime verification step (T24 Step 1).
- **Type consistency:** `Settings` fields ↔ env vars ↔ compose; `RawItem` ↔ adapters ↔ `insert_new_items`; `Enrichment/Delta/DigestSchema/BattlecardGen/ChatAnswer` ↔ stages ↔ API dicts ↔ `frontend/src/types.ts`; `REFRESH_STATE` shape ↔ `/api/refresh/status` ↔ `Meta.refresh_state`. `create_app(settings)` signature consistent across all API tests.
