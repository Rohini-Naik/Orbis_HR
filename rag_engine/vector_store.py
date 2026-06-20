import chromadb

from rag_engine.config import CHROMA_DB_DIR, COLLECTION_NAME


def get_chroma_client():
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))


def get_policy_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_policy_collection():
    client = get_chroma_client()

    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
) -> int:
    if not chunks:
        return 0

    collection = get_policy_collection()

    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[
            {
                "source": chunk["source"],
                "page": chunk["page"],
                "category": chunk["category"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ],
        embeddings=embeddings,
    )

    return len(chunks)


def delete_by_source(source: str) -> None:
    """Remove all chunks that came from a given policy file."""
    get_policy_collection().delete(where={"source": source})


def count_chunks() -> int:
    return get_policy_collection().count()


def count_by_source(source: str) -> int:
    result = get_policy_collection().get(where={"source": source}, include=[])
    return len(result.get("ids", []))


def search_chunks(
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    collection = get_policy_collection()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    matches = []

    for chunk_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):
        matches.append(
            {
                "id": chunk_id,
                "text": document,
                "source": metadata.get("source"),
                "page": metadata.get("page"),
                "category": metadata.get("category"),
                "distance": distance,
                "score": round(1 - distance, 4),
            }
        )

    return matches