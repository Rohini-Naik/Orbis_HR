"""First-run registration of policy files already on disk.

No user accounts are seeded. The first administrator is created deliberately by
an operator on the machine:

    python -m app.provision create-admin --email hr.head@orbis.com

so that no account with a known password ever exists by default.
"""
from app.db import execute, query_one
from rag_engine import vector_store
from rag_engine.config import POLICY_DOCUMENTS_DIR
from rag_engine.document_loader import SUPPORTED_EXTENSIONS, infer_category


def seed_policy_files() -> None:
    """Register policy files already present on disk so the Policy Library
    reflects the pre-built index."""
    if not POLICY_DOCUMENTS_DIR.exists():
        return
    if query_one("SELECT COUNT(*) AS n FROM policy_files")["n"] > 0:
        return
    for path in sorted(POLICY_DOCUMENTS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        execute(
            "INSERT IGNORE INTO policy_files (filename, category, chunks, uploaded_by) "
            "VALUES (%s, %s, %s, %s)",
            (path.name, infer_category(path.name),
             vector_store.count_by_source(path.name), "system"),
        )
