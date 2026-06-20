from functools import lru_cache
import os
from typing import Any

from rag_engine.settings import HUGGINGFACE_API_KEY, EMBEDDING_MODEL_NAME


@lru_cache(maxsize=1)
def get_embedding_backend() -> Any:
    """Return either a local SentenceTransformer model or a Hugging Face InferenceClient.

    Behavior:
    - If EMBEDDING_MODEL_NAME starts with 'sentence-transformers/', load local SentenceTransformer.
    - Otherwise attempt to instantiate a Hugging Face Inference client (requires HUGGINGFACE_API_KEY).
    """
    if EMBEDDING_MODEL_NAME.startswith("sentence-transformers/"):
        try:
                from sentence_transformers import SentenceTransformer

                return SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as exc:
            raise RuntimeError(f"Failed to load SentenceTransformer model: {exc}")

    # use Hugging Face Inference API
    try:
        from huggingface_hub import InferenceClient
    except Exception as exc:
        raise RuntimeError("huggingface_hub not installed; install it to use HF Inference embeddings")

    hf_token = HUGGINGFACE_API_KEY
    if not hf_token:
        raise RuntimeError("HUGGINGFACE_API_KEY is not set in environment; required for HF Inference embeddings")

    return InferenceClient(token=hf_token)


def embed_texts(texts: list[str]) -> list[list[float]]:
    backend = get_embedding_backend()

    if EMBEDDING_MODEL_NAME.startswith("sentence-transformers/"):
        embeddings = backend.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    # Hugging Face Inference client path
    try:
        from rag_engine.hf_utils import embeddings_call

        resp = embeddings_call(backend, EMBEDDING_MODEL_NAME, texts)
    except Exception:
        # Fall back to attempting a few possible response shapes directly
        resp = None

    embeddings = []
    if resp is None:
        raise RuntimeError("Failed to call HF embeddings API")

    if isinstance(resp, dict) and "embedding" in resp:
        return [resp["embedding"]]

    if isinstance(resp, list):
        for item in resp:
            if isinstance(item, dict) and "embedding" in item:
                embeddings.append(item["embedding"])
            elif isinstance(item, list):
                embeddings.append(item)
            else:
                raise RuntimeError("Unexpected embeddings response from Hugging Face Inference API")

    return embeddings


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]