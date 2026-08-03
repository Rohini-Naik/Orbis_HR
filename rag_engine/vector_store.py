"""The policy index, backed by LangChain's Chroma integration.

Going through `langchain_chroma` rather than the raw client means the same
object can be handed to a retriever and dropped into a chain, instead of every
caller marshalling vectors and metadata itself.

Search results are returned as plain dictionaries. Callers outside this module
(the answer generator, the policy library, the startup index check) only need
text and provenance, and keeping them free of LangChain types leaves the
storage layer replaceable.
"""
import logging
from functools import lru_cache
from typing import Any, Dict, List

from langchain_core.documents import Document

from rag_engine.config import CHROMA_DB_DIR, COLLECTION_NAME
from rag_engine.embeddings import get_embeddings

logger = logging.getLogger("orbis.vectorstore")


@lru_cache(maxsize=1)
def get_store():
    """The persistent collection, created on first use."""
    from langchain_chroma import Chroma

    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DB_DIR),
        # Cosine matches how the embeddings are normalised; Chroma defaults to
        # squared L2, which would rank differently.
        collection_metadata={"hnsw:space": "cosine"},
    )


def reset_policy_collection() -> None:
    """Drop every chunk. Used by a full re-index."""
    store = get_store()
    try:
        store.delete_collection()
    except Exception:
        logger.debug("No existing collection to drop", exc_info=True)
    get_store.cache_clear()
    get_store()


def upsert_chunks(chunks: List[Document]) -> int:
    """Store chunks under their stable ids, replacing any with the same id."""
    if not chunks:
        return 0
    get_store().add_documents(
        documents=chunks, ids=[c.metadata["chunk_id"] for c in chunks]
    )
    return len(chunks)


def delete_by_source(source: str) -> None:
    """Remove every chunk that came from one policy file."""
    try:
        get_store().delete(where={"source": source})
    except Exception:
        logger.warning("Could not clear existing chunks for %s", source, exc_info=True)


def count_chunks() -> int:
    return get_store()._collection.count()


def count_by_source(source: str) -> int:
    result = get_store()._collection.get(where={"source": source}, include=[])
    return len(result.get("ids", []))


def _to_match(doc: Document, score: float, index: int) -> Dict[str, Any]:
    """Flatten a scored Document into the shape the rest of the app expects."""
    meta = doc.metadata or {}
    return {
        "id": meta.get("chunk_id", f"chunk_{index}"),
        "text": doc.page_content,
        "source": meta.get("source"),
        "page": meta.get("page"),
        "category": meta.get("category"),
        "company": meta.get("company"),
        "distance": score,
        # Chroma returns cosine distance; 1 - distance reads as similarity.
        "score": round(1 - score, 4),
    }


def search_chunks(query: str, top_k: int) -> List[Dict[str, Any]]:
    """The `top_k` chunks closest to the query, most similar first."""
    try:
        scored = get_store().similarity_search_with_score(query, k=top_k)
    except Exception as exc:
        # Most often a dimension mismatch: the embedding model changed but the
        # index was not rebuilt. Say so instead of surfacing the raw error.
        raise RuntimeError(
            f"Policy search failed: {exc}. If EMBEDDING_MODEL_NAME changed, "
            "re-index with: python -m rag_engine.maintenance"
        ) from exc
    return [_to_match(doc, score, i) for i, (doc, score) in enumerate(scored)]
