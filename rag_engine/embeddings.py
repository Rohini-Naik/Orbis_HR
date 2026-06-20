"""Local embedding model (sentence-transformers).

Embeddings are computed locally so policy/employee text never leaves the
network. The generative models (RAG answers, NL->SQL) are called remotely —
see llm.py.
"""
from functools import lru_cache

from rag_engine.settings import EMBEDDING_MODEL_NAME


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _model().encode(texts, normalize_embeddings=True).tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
