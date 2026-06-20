"""Seed demo accounts on first run so the API is usable out of the box.

    rohit.verma@acmecorp.com  / demo1234   (HR admin, org-wide access)
    priya.sharma@acmecorp.com / demo1234   (employee, scoped to EmployeeID 2001)
"""
from app.auth import hash_password
from app.db import execute, query_one
from rag_engine import vector_store
from rag_engine.config import POLICY_DOCUMENTS_DIR
from rag_engine.document_loader import SUPPORTED_EXTENSIONS, infer_category

# email, password, full_name, role, employee_id, department
DEMO_USERS = [
    ("rohit.verma@acmecorp.com", "demo1234", "Rohit Verma", "admin", None, "Human Resources"),
    ("priya.sharma@acmecorp.com", "demo1234", "Priya Sharma", "employee", 2001, "Engineering"),
]


def seed_users() -> None:
    if query_one("SELECT COUNT(*) AS n FROM users")["n"] > 0:
        return
    for email, password, full_name, role, employee_id, department in DEMO_USERS:
        execute(
            "INSERT INTO users (email, password_hash, full_name, role, employee_id, department) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (email, hash_password(password), full_name, role, employee_id, department),
        )


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
