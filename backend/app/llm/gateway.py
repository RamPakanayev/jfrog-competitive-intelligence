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
        self._ollama_probe: bool | None = None

    def _key_for(self, provider: str) -> str:
        secret = {"anthropic": self.s.anthropic_api_key,
                  "openai": self.s.openai_api_key,
                  "gemini": self.s.gemini_api_key}.get(provider)
        return secret.get_secret_value() if secret else ""

    def _has_key(self, provider: str) -> bool:
        return bool(self._key_for(provider))

    def _ollama_up(self) -> bool:
        if self._ollama_probe is None:
            try:
                self._ollama_probe = (
                    httpx.get(f"{self.s.ollama_base_url}/api/tags", timeout=1.5).status_code == 200)
            except Exception:  # noqa: BLE001 - liveness probe must never raise
                self._ollama_probe = False
        return self._ollama_probe

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
                except Exception as e:  # noqa: BLE001 - fail-soft: any provider/network error -> try next provider
                    log.warning("provider %s failed: %s", provider, e)
                    break
        return None
