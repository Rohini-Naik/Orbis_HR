"""Policy Library: upload + auto-index, list/search, view, delete (un-index),
and dashboard stats."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.db import execute, query_all, query_one
from app.services import audit_service
from rag_engine import rag_pipeline, vector_store
from rag_engine.config import POLICY_DOCUMENTS_DIR
from rag_engine.document_loader import (
    SUPPORTED_EXTENSIONS,
    infer_category,
    load_document,
)


def upload(filename: str, content: bytes, user: Dict[str, Any]) -> Dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '{suffix}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    POLICY_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = POLICY_DOCUMENTS_DIR / Path(filename).name
    path.write_bytes(content)

    category = infer_category(path.name)
    chunks = rag_pipeline.index_file(path)

    execute(
        "INSERT INTO policy_files (filename, category, chunks, size_bytes, status, uploaded_by) "
        "VALUES (%s, %s, %s, %s, 'indexed', %s) AS new "
        "ON DUPLICATE KEY UPDATE category=new.category, chunks=new.chunks, "
        "size_bytes=new.size_bytes, status='indexed', uploaded_by=new.uploaded_by, "
        "uploaded_at=NOW()",
        (path.name, category, chunks, len(content), user.get("email")),
    )
    audit_service.log_event("upload", user=user, question=path.name)
    return query_one("SELECT * FROM policy_files WHERE filename = %s", (path.name,))


def get_file_path(file_id: int) -> Path:
    row = query_one("SELECT filename FROM policy_files WHERE id = %s", (file_id,))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    path = POLICY_DOCUMENTS_DIR / row["filename"]
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing on disk")
    return path


def list_files(
    search: Optional[str] = None, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM policy_files"
    clauses, params = [], []
    if search:
        clauses.append("filename LIKE %s")
        params.append(f"%{search}%")
    if category:
        clauses.append("category = %s")
        params.append(category)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY uploaded_at DESC"
    return query_all(query, params)


def get_file(file_id: int) -> Dict[str, Any]:
    row = query_one("SELECT * FROM policy_files WHERE id = %s", (file_id,))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    path = POLICY_DOCUMENTS_DIR / row["filename"]
    pages = load_document(path) if path.exists() else []
    return {**row, "content": "\n\n".join(p["text"] for p in pages)}


def delete(file_id: int, user: Dict[str, Any]) -> None:
    row = query_one("SELECT * FROM policy_files WHERE id = %s", (file_id,))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    rag_pipeline.delete_file(row["filename"])
    (POLICY_DOCUMENTS_DIR / row["filename"]).unlink(missing_ok=True)
    execute("DELETE FROM policy_files WHERE id = %s", (file_id,))
    audit_service.log_event("delete", user=user, question=row["filename"])


def stats() -> Dict[str, Any]:
    total = query_one("SELECT COUNT(*) AS n FROM policy_files")["n"]
    return {
        "total_policies": total,
        "indexed_chunks": vector_store.count_chunks(),
        "queries_served": audit_service.count_queries(),
        "accuracy_rate": audit_service.accuracy_rate(),
    }
