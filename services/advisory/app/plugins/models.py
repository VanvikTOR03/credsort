"""LanguageModel plug-ins (ADR-0003, ADR-0009). The model is configuration; the template model is the always-available fallback."""
from __future__ import annotations

import json
from typing import Protocol

import httpx

from credsort_common.config import env

from ..domain import text as T


class LanguageModel(Protocol):
    name: str
    version: str

    def explain(self, kind: str, context: dict) -> dict: ...


class TemplateModel:
    """Deterministic explanations; works offline and costs nothing."""
    name, version = "template", "t1"

    def explain(self, kind: str, context: dict) -> dict:
        return T.explain_scenario(context) if kind == "scenario" else T.explain_assessment(context)


PROMPT = ("You explain a Swiss SME's preliminary financial assessment in plain, neutral English. Use ONLY the numbers in the JSON context; never "
          "calculate new numbers, never promise credit approval, never advise manipulating financial statements. Reply as JSON with keys "
          "headline (string), summary (string), strengths (list of strings), concerns (list of strings), data_gaps (list), suggestions (list).")


class LlmApiModel:
    """OpenAI-compatible chat-completions endpoint (any hosted model or a self-hosted small model). Configured through env."""

    def __init__(self, base_url: str, model: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self.name, self.version = f"llm:{model}", "p1"
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(15.0, connect=3.0), transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
        self._model = model

    def explain(self, kind: str, context: dict) -> dict:
        resp = self._client.post("/chat/completions", json={"model": self._model, "response_format": {"type": "json_object"}, "temperature": 0,
                                                            "messages": [{"role": "system", "content": PROMPT},
                                                                         {"role": "user", "content": json.dumps({"kind": kind, "context": context}, default=str)}]})
        resp.raise_for_status()
        out = json.loads(resp.json()["choices"][0]["message"]["content"])
        return {k: out.get(k, [] if k not in ("headline", "summary") else "") for k in ("headline", "summary", "strengths", "concerns", "data_gaps", "suggestions")}


def build_chain() -> list[LanguageModel]:
    chain: list[LanguageModel] = []
    if env("LLM_BASE_URL") and env("LLM_MODEL"):
        chain.append(LlmApiModel(env("LLM_BASE_URL") or "", env("LLM_MODEL") or "", env("LLM_API_KEY", "") or ""))
    chain.append(TemplateModel())
    return chain
