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
    def load(cls, config_dir: Path) -> AppConfig:
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
