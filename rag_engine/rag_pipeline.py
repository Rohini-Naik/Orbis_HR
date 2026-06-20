from rag_engine.config import DEFAULT_TOP_K
from rag_engine.document_loader import load_policy_documents
from rag_engine.embeddings import embed_query, embed_texts
from rag_engine.text_splitter import chunk_documents
from rag_engine.vector_store import (
    reset_policy_collection,
    search_chunks,
    upsert_chunks,
)


def index_policy_documents(reset: bool = True) -> dict:
    documents = load_policy_documents()
    chunks = chunk_documents(documents)

    if reset:
        reset_policy_collection()

    embeddings = embed_texts([chunk["text"] for chunk in chunks])
    indexed_count = upsert_chunks(chunks, embeddings)

    return {
        "documents_loaded": len(documents),
        "chunks_indexed": indexed_count,
    }


def search_policy(
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    query_embedding = embed_query(question)
    matches = search_chunks(
        query_embedding=query_embedding,
        top_k=top_k,
    )

    return {
        "question": question,
        "top_k": top_k,
        "results": matches,
    }
