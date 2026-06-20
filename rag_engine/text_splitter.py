import hashlib
import re

from rag_engine.config import CHUNK_OVERLAP, CHUNK_SIZE


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    text = clean_text(text)

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            last_break = max(
                chunk.rfind("\n"),
                chunk.rfind(". "),
                chunk.rfind(" "),
            )

            if last_break > chunk_size * 0.5:
                end = start + last_break + 1
                chunk = text[start:end]

        chunk = chunk.strip()

        if chunk:
            chunks.append(chunk)

        next_start = end - overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def make_chunk_id(
    source: str,
    page: int,
    chunk_index: int,
    text: str,
) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    safe_source = re.sub(r"[^a-zA-Z0-9]+", "_", source).strip("_").lower()

    return f"{safe_source}_p{page}_c{chunk_index}_{digest}"


def chunk_documents(documents: list[dict]) -> list[dict]:
    chunks = []

    for document in documents:
        text_chunks = split_text(document["text"])

        for index, chunk_text in enumerate(text_chunks):
            chunks.append(
                {
                    "id": make_chunk_id(
                        source=document["source"],
                        page=document["page"],
                        chunk_index=index,
                        text=chunk_text,
                    ),
                    "text": chunk_text,
                    "source": document["source"],
                    "page": document["page"],
                    "category": document["category"],
                    "chunk_index": index,
                }
            )

    return chunks