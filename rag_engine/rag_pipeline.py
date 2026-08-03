"""Indexing and retrieval over the policy corpus.

Composes the loader, splitter and vector store rather than doing work itself,
so each stage stays independently testable.
"""
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.documents import Document

from rag_engine.config import DEFAULT_TOP_K
from rag_engine.document_loader import load_document, load_policy_documents
from rag_engine.text_splitter import chunk_documents
from rag_engine.vector_store import (
    delete_by_source,
    get_store,
    reset_policy_collection,
    search_chunks,
    upsert_chunks,
)


def index_policy_documents(reset: bool = True) -> Dict[str, int]:
    """(Re)index every file in the policy folder."""
    documents: List[Document] = load_policy_documents()
    if reset:
        reset_policy_collection()
    indexed = upsert_chunks(chunk_documents(documents))
    return {"documents_loaded": len(documents), "chunks_indexed": indexed}


def index_file(file_path: Path) -> int:
    """Index a single uploaded file, replacing any earlier version of it.

    Chunk ids are derived from the text, so a revised document produces new ids
    and an upsert alone would leave the previous version's chunks in the index —
    the assistant would then cite a superseded policy alongside the current one.
    Clearing by source first makes re-uploading a genuine replacement.
    """
    path = Path(file_path)
    delete_by_source(path.name)
    return upsert_chunks(chunk_documents(load_document(path)))


def delete_file(source: str) -> None:
    """Un-index a policy file by its source name."""
    delete_by_source(source)


def get_retriever(top_k: int = DEFAULT_TOP_K):
    """The corpus as a LangChain retriever, for composing into a chain."""
    return get_store().as_retriever(search_kwargs={"k": top_k})


def search_policy(question: str, top_k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
    """Retrieve with scores, for callers that display relevance."""
    return {
        "question": question,
        "top_k": top_k,
        "results": search_chunks(question, top_k=top_k),
    }
