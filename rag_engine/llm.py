"""Hosted LLM calls, behind a provider switch.

Embeddings run locally (see embeddings.py) so document text stays on-prem. The
generative models — routing, RAG answers, NL->SQL and verification — are called
remotely.

Two providers are supported and both speak the same chat-completions shape, so
the rest of the codebase never learns which is in use:

    LLM_PROVIDER=groq           (default when GROQ_API_KEY is set)
    LLM_PROVIDER=huggingface

Switching is an environment change, not a code change — which matters because
a provider running out of credits should not require touching the application.
"""
import logging
from functools import lru_cache
from typing import Any, Dict, List

import httpx

from rag_engine import settings

logger = logging.getLogger("orbis.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class LLMError(RuntimeError):
    """Raised when the provider cannot serve the request."""


# ----------------------------------------------------------------------- groq
@lru_cache(maxsize=1)
def _groq_client() -> httpx.Client:
    if not settings.GROQ_API_KEY:
        raise LLMError(
            "GROQ_API_KEY is not set. Add it to .env, or set LLM_PROVIDER=huggingface."
        )
    return httpx.Client(
        timeout=TIMEOUT,
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
    )


def _groq_complete(messages: List[Dict[str, str]], model: str,
                   max_tokens: int, temperature: float) -> str:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    # Reasoning models spend the token budget thinking and can return empty
    # content when it runs out. Capping the effort keeps the answer itself
    # affordable — and is markedly faster.
    if settings.GROQ_REASONING_EFFORT:
        payload["reasoning_effort"] = settings.GROQ_REASONING_EFFORT

    response = _groq_client().post(GROQ_URL, json=payload)

    # Models that do not accept the parameter reject it outright; drop it and
    # retry rather than failing the request.
    if response.status_code == 400 and "reasoning_effort" in response.text:
        payload.pop("reasoning_effort", None)
        response = _groq_client().post(GROQ_URL, json=payload)

    if response.status_code != 200:
        if response.status_code == 401:
            raise LLMError("Groq rejected the API key (401). Check GROQ_API_KEY in .env.")
        if response.status_code == 429:
            raise LLMError("Groq rate limit reached (429). Wait a moment and retry.")
        raise LLMError(f"Groq returned {response.status_code}: {response.text[:300]}")

    message = response.json()["choices"][0]["message"]
    content = (message.get("content") or "").strip()
    if not content:
        raise LLMError(
            "Groq returned an empty response — the model likely spent its token "
            "budget reasoning. Raise max_tokens or lower GROQ_REASONING_EFFORT."
        )
    return content


# ---------------------------------------------------------------- huggingface
@lru_cache(maxsize=1)
def _hf_client():
    from huggingface_hub import InferenceClient

    if not settings.HUGGINGFACE_API_KEY:
        raise LLMError("HUGGINGFACE_API_KEY is not set; required for hosted LLM calls")
    return InferenceClient(token=settings.HUGGINGFACE_API_KEY)


def _hf_complete(messages: List[Dict[str, str]], model: str,
                 max_tokens: int, temperature: float) -> str:
    response = _hf_client().chat_completion(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ------------------------------------------------------------------ dispatch
def _complete(messages: List[Dict[str, str]], model: str,
              max_tokens: int, temperature: float) -> str:
    provider = settings.LLM_PROVIDER
    try:
        if provider == "groq":
            return _groq_complete(messages, model, max_tokens, temperature)
        return _hf_complete(messages, model, max_tokens, temperature)
    except LLMError:
        raise
    except Exception as exc:  # network, decoding, provider-specific errors
        raise LLMError(f"{provider} request failed: {exc}") from exc


def chat(prompt: str, model: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
    """Single-turn instruction call."""
    return _complete([{"role": "user", "content": prompt}], model, max_tokens, temperature)


def converse(messages: List[Dict[str, Any]], model: str,
             max_tokens: int = 400, temperature: float = 0.3) -> str:
    """Multi-turn chat (system + history + user) for general conversation."""
    return _complete(messages, model, max_tokens, temperature)


def complete(prompt: str, model: str, max_tokens: int = 300) -> str:
    """Greedy single-turn completion."""
    return chat(prompt, model=model, max_tokens=max_tokens, temperature=0.0)


def available_models() -> List[str]:
    """Model ids the configured provider will serve (Groq only)."""
    if settings.LLM_PROVIDER != "groq":
        return []
    response = _groq_client().get("https://api.groq.com/openai/v1/models")
    response.raise_for_status()
    return sorted(m["id"] for m in response.json().get("data", []))
