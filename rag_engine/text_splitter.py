"""Chunking, via LangChain's recursive splitter.

`RecursiveCharacterTextSplitter` tries progressively finer separators —
paragraph, line, sentence, word — so a chunk boundary lands at a natural break
rather than mid-sentence. Chunks overlap because a sentence split across a
boundary would otherwise be retrievable from neither side.
"""
import hashlib
import re
from functools import lru_cache
from typing import Dict, List, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_engine.config import CHUNK_OVERLAP, CHUNK_SIZE


@lru_cache(maxsize=1)
def get_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )


def clean_text(text: str) -> str:
    """Normalise whitespace so chunk boundaries are not decided by stray spacing."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def make_chunk_id(source: str, page: int, chunk_index: int, text: str) -> str:
    """Stable, content-derived id.

    Including a hash of the text means an edited document produces different
    ids — which is why re-indexing clears a document's existing chunks first,
    rather than relying on an upsert to displace them.
    """
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    safe_source = re.sub(r"[^a-zA-Z0-9]+", "_", source).strip("_").lower()
    return f"{safe_source}_p{page}_c{chunk_index}_{digest}"


def chunk_documents(documents: List[Document]) -> List[Document]:
    """Split pages into chunks, carrying each page's metadata onto its chunks."""
    cleaned = []
    for doc in documents:
        text = clean_text(doc.page_content)
        if text:
            cleaned.append(Document(page_content=text, metadata=dict(doc.metadata)))

    chunks = get_splitter().split_documents(cleaned)

    # Number chunks within each page, then give each a stable id.
    counters: Dict[Tuple[str, int], int] = {}
    for chunk in chunks:
        key = (chunk.metadata.get("source", "unknown"), chunk.metadata.get("page", 1))
        index = counters[key] = counters.get(key, -1) + 1
        chunk.metadata["chunk_index"] = index
        chunk.metadata["chunk_id"] = make_chunk_id(key[0], key[1], index, chunk.page_content)
    return chunks


def chunk_ids(chunks: List[Document]) -> List[str]:
    return [c.metadata["chunk_id"] for c in chunks]
