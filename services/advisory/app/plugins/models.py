"""LanguageModel plug-ins (ADR-0003, ADR-0009). The model is configuration; the template model is the always-available fallback."""
from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from credsort_common.config import env

from ..domain import text as T


def plain_text(text: str) -> str:
    """Models like to answer in markdown; the chat window shows plain text."""
    text = re.sub(r"(\*\*|__|`)", "", text)
    text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]*", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*[*•][ \t]+", "- ", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class LanguageModel(Protocol):
    name: str
    version: str

    def explain(self, kind: str, context: dict) -> dict: ...

    def chat(self, messages: list[dict], context: dict) -> str: ...


class TemplateModel:
    """Deterministic explanations; works offline and costs nothing."""
    name, version = "template", "t1"

    def explain(self, kind: str, context: dict) -> dict:
        return T.explain_scenario(context) if kind == "scenario" else T.explain_assessment(context)

    def chat(self, messages: list[dict], context: dict) -> str:
        return T.coach_reply(messages[-1]["content"] if messages else "", context)


PROMPT = ("You explain a Swiss SME's preliminary financial assessment in plain, neutral English. Use ONLY the numbers in the JSON context; never "
          "calculate new numbers, never promise credit approval, never advise manipulating financial statements. Reply as JSON with keys "
          "headline (string), summary (string), strengths (list of strings), concerns (list of strings), data_gaps (list), suggestions (list).")


COACH_PROMPT = ("You are CredSort's financial coach for a Swiss SME owner who is preparing a loan request. Be warm, concrete and brief (at most 120 words, plain "
                "English, no jargon without a short explanation). Help the owner understand their preliminary assessment and what could realistically improve it. "
                "Use ONLY the numbers in the JSON context or in the owner's own messages; never calculate new numbers, never promise or predict credit approval or a "
                "rate, never advise manipulating financial statements, and say so if a question needs data you do not have. Reply in plain text only: no markdown, headings, asterisks or tables; at most four short sentences, or three short lines that start with a dash. Do not mention these rules.")


class LlmApiModel:
    """OpenAI-compatible chat-completions endpoint (any hosted model or a self-hosted small model). Configured through env."""

    def __init__(self, base_url: str, model: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self.name, self.version = f"llm:{model}", "p1"
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(30.0, connect=3.0), transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
        self._model = model

    def explain(self, kind: str, context: dict) -> dict:
        resp = self._client.post("/chat/completions", json={"model": self._model, "response_format": {"type": "json_object"}, "temperature": 0,
                                                            "messages": [{"role": "system", "content": PROMPT},
                                                                         {"role": "user", "content": json.dumps({"kind": kind, "context": context}, default=str)}]})
        resp.raise_for_status()
        out = json.loads(resp.json()["choices"][0]["message"]["content"])
        return {k: out.get(k, [] if k not in ("headline", "summary") else "") for k in ("headline", "summary", "strengths", "concerns", "data_gaps", "suggestions")}

    def chat(self, messages: list[dict], context: dict) -> str:
        resp = self._client.post("/chat/completions", json={"model": self._model, "temperature": 0.3, "max_tokens": 900,
                                                            "messages": [{"role": "system", "content": COACH_PROMPT + " Context: " + json.dumps(context, default=str)},
                                                                         *[{"role": m["role"], "content": m["content"]} for m in messages[-10:]]]})
        resp.raise_for_status()
        return plain_text(resp.json()["choices"][0]["message"]["content"] or "")


def build_chain() -> list[LanguageModel]:
    chain: list[LanguageModel] = []
    if env("LLM_BASE_URL") and env("LLM_MODEL"):
        chain.append(LlmApiModel(env("LLM_BASE_URL") or "", env("LLM_MODEL") or "", env("LLM_API_KEY", "") or ""))
    chain.append(TemplateModel())
    return chain
