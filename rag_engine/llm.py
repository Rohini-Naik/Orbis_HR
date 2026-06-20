"""Server-hosted LLM calls via the Hugging Face Inference API.

Embeddings run locally (see embeddings.py) so document text stays on-prem.
The larger generative models — RAG answers and NL->SQL — are called remotely
instead of being hosted locally.
"""
from functools import lru_cache

from huggingface_hub import InferenceClient

from rag_engine import settings


@lru_cache(maxsize=1)
def _client() -> InferenceClient:
    if not settings.HUGGINGFACE_API_KEY:
        raise RuntimeError("HUGGINGFACE_API_KEY is not set; required for hosted LLM calls")
    return InferenceClient(token=settings.HUGGINGFACE_API_KEY)


def chat(prompt: str, model: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
    """Call an instruction-tuned chat model (e.g. Llama-3.1-8B-Instruct)."""
    resp = _client().chat_completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def converse(messages: list[dict], model: str, max_tokens: int = 400, temperature: float = 0.3) -> str:
    """Multi-turn chat (system + history + user) for general conversation."""
    resp = _client().chat_completion(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def complete(prompt: str, model: str, max_tokens: int = 300) -> str:
    """Call a text-completion model (e.g. sqlcoder) with greedy decoding."""
    return _client().text_generation(
        prompt,
        model=model,
        max_new_tokens=max_tokens,
        do_sample=False,
    ).strip()
