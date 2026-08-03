"""Local embedding model (sentence-transformers).

Embeddings are computed locally so policy/employee text never leaves the
network. The generative models (RAG answers, NL->SQL) are called remotely —
see llm.py.
"""
import logging
import time
from functools import lru_cache

from rag_engine.settings import EMBEDDING_MODEL_NAME


logger = logging.getLogger("orbis.embeddings")


@lru_cache(maxsize=1)
def _model():
    """Load the embedding model once per process.

    Loading takes tens of seconds, so it is cached for the process lifetime and
    warmed at startup — otherwise the first policy question pays the whole cost.
    """
    from sentence_transformers import SentenceTransformer

    started = time.perf_counter()
    try:
        # Once the weights are on disk there is nothing to fetch, and checking
        # the Hub anyway costs about ten seconds and a network dependency the
        # rest of the retrieval path does not have.
        model = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
        source = "local cache"
    except Exception:
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        source = "Hugging Face Hub"
    logger.info(
        "Embedding model %s loaded from %s in %.1fs",
        EMBEDDING_MODEL_NAME, source, time.perf_counter() - started,
    )
    return model


def warm_up() -> None:
    """Force the model into memory. Called at startup so no request waits on it."""
    embed_query("warm up")


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _model().encode(texts, normalize_embeddings=True).tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
