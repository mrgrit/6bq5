"""Thin LLM bridge.

Talks to:
  - Ollama (LLM_BASE_URL, LLM_MODEL) — same convention CCC uses.
  - Bastion FastAPI (BASTION_URL=http://localhost:9100) for KG-aware chat.

Both calls are best-effort. If neither is reachable we return a deterministic
mock so the UI keeps working in offline / demo mode.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx


LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b")
BASTION_URL = os.environ.get("BASTION_URL", "http://localhost:9100")
BASTION_KEY = os.environ.get("BASTION_API_KEY", "ccc-api-key-2026")


def _mock_completion(prompt: str) -> str:
    return (
        f"[mock LLM — set LLM_BASE_URL]\n"
        f"reasoning: prompt length={len(prompt)} chars\n"
        f"answer: (placeholder) the platform is in offline mode."
    )


def complete(prompt: str, system: str | None = None, timeout: float = 30.0) -> str:
    """Sync, single-shot, non-streaming."""
    url = f"{LLM_BASE_URL.rstrip('/')}/api/chat"
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = {"model": LLM_MODEL, "messages": msgs, "stream": False}
    try:
        with httpx.Client(timeout=timeout) as cli:
            r = cli.post(url, json=body)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content") or data.get("response") or ""
    except Exception as e:
        return f"{_mock_completion(prompt)}\n# error: {e!s}"


def craft_attack(target: dict, recipe_hint: str, kg_context: str) -> dict:
    """Use the LLM as a red-team helper: produce a tailored attack plan."""
    sys = (
        "You are a red-team operator authorized for an isolated cyber range. "
        "Given a target asset and KG context, craft a concrete attack plan "
        "(recon → initial access → lateral → impact) with exact commands. "
        "Output JSON: {\"plan\":[{\"step\":1,\"phase\":\"recon\",\"command\":\"...\",\"why\":\"...\"}], \"poison_tip\":\"...\"}."
    )
    prompt = (
        f"# target\n{json.dumps(target, ensure_ascii=False)}\n"
        f"# recipe hint\n{recipe_hint}\n"
        f"# kg context (poisoned)\n{kg_context}\n"
    )
    raw = complete(prompt, system=sys)
    try:
        # crude JSON salvage
        s = raw.find("{")
        e = raw.rfind("}")
        if s >= 0 and e > s:
            return {"raw": raw, "plan": json.loads(raw[s : e + 1])}
    except Exception:
        pass
    return {"raw": raw, "plan": None}


def bastion_chat(prompt: str, timeout: float = 60.0) -> dict:
    """Proxy to bastion API /chat (KG-aware). Falls back to direct LLM."""
    url = f"{BASTION_URL.rstrip('/')}/chat"
    headers = {"X-API-Key": BASTION_KEY, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as cli:
            r = cli.post(url, headers=headers, json={"message": prompt})
            r.raise_for_status()
            return {"source": "bastion", "data": r.json()}
    except Exception as e:
        return {
            "source": "fallback_llm",
            "error": str(e),
            "data": {"response": complete(prompt)},
        }


def health() -> dict:
    out = {"llm_base_url": LLM_BASE_URL, "model": LLM_MODEL, "bastion_url": BASTION_URL}
    try:
        with httpx.Client(timeout=3.0) as cli:
            r = cli.get(f"{LLM_BASE_URL.rstrip('/')}/api/tags")
            out["llm_reachable"] = r.status_code == 200
    except Exception as e:
        out["llm_reachable"] = False
        out["llm_error"] = str(e)
    try:
        with httpx.Client(timeout=3.0) as cli:
            r = cli.get(f"{BASTION_URL.rstrip('/')}/health", headers={"X-API-Key": BASTION_KEY})
            out["bastion_reachable"] = r.status_code == 200
    except Exception as e:
        out["bastion_reachable"] = False
        out["bastion_error"] = str(e)
    return out
