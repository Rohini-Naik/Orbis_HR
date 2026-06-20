from pathlib import Path

from rag_engine.config import DEFAULT_TOP_K
from rag_engine.document_loader import load_document, load_policy_documents
from rag_engine.embeddings import embed_query, embed_texts
from rag_engine.text_splitter import chunk_documents
from rag_engine.vector_store import (
    delete_by_source,
    reset_policy_collection,
    search_chunks,
    upsert_chunks,
)


def _embed_and_upsert(chunks: list[dict]) -> int:
    if not chunks:
        return 0
    embeddings = embed_texts([chunk["text"] for chunk in chunks])
    return upsert_chunks(chunks, embeddings)


def index_policy_documents(reset: bool = True) -> dict:
    """Full (re)index of every file in the policy folder."""
    documents = load_policy_documents()
    if reset:
        reset_policy_collection()
    indexed = _embed_and_upsert(chunk_documents(documents))
    return {"documents_loaded": len(documents), "chunks_indexed": indexed}


def index_file(file_path: Path) -> int:
    """Incrementally index a single newly-uploaded file (no full reset)."""
    chunks = chunk_documents(load_document(Path(file_path)))
    return _embed_and_upsert(chunks)


def delete_file(source: str) -> None:
    """Un-index a policy file by its source name."""
    delete_by_source(source)


def search_policy(question: str, top_k: int = DEFAULT_TOP_K) -> dict:
    matches = search_chunks(embed_query(question), top_k=top_k)
    return {"question": question, "top_k": top_k, "results": matches}
