"""Application-state storage (MySQL).

Holds everything the app itself owns — users, sessions, conversations,
messages, the audit trail and policy-file metadata — in the read-write
`orbis_app` database. The HR employee data lives separately in `orbis_hr`
and is only ever read through the read-only `orbis_user`.
"""
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence

import mysql.connector
from mysql.connector import pooling

from rag_engine import settings

_POOL: Optional[pooling.MySQLConnectionPool] = None

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        email         VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name     VARCHAR(255) NOT NULL,
        role          VARCHAR(20) NOT NULL,
        employee_id   VARCHAR(20),
        department    VARCHAR(100),
        is_active     TINYINT NOT NULL DEFAULT 1,
        created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (role IN ('admin', 'employee'))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        token      VARCHAR(255) PRIMARY KEY,
        user_id    INT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        user_id    INT NOT NULL,
        title      VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        conversation_id INT NOT NULL,
        role            VARCHAR(20) NOT NULL,
        content         TEXT NOT NULL,
        created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
        CHECK (role IN ('user', 'assistant'))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id                    INT AUTO_INCREMENT PRIMARY KEY,
        user_id               INT,
        username              VARCHAR(255),
        role                  VARCHAR(20),
        action                VARCHAR(50) NOT NULL,
        question              TEXT,
        route                 VARCHAR(20),
        sql_text              TEXT,
        sources               TEXT,
        confidence            DOUBLE,
        latency_ms            INT,
        hallucination_blocked TINYINT NOT NULL DEFAULT 0,
        created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS invites (
        token         VARCHAR(255) PRIMARY KEY,
        employee_id   VARCHAR(20) NOT NULL,
        company_email VARCHAR(255) NOT NULL,
        full_name     VARCHAR(255) NOT NULL,
        expires_at    DATETIME NOT NULL,
        used_at       DATETIME NULL,
        created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_invites_email (company_email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS password_resets (
        token      VARCHAR(255) PRIMARY KEY,
        user_id    INT NOT NULL,
        expires_at DATETIME NOT NULL,
        used_at    DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        INDEX idx_resets_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_files (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        filename    VARCHAR(512) NOT NULL UNIQUE,
        category    VARCHAR(50),
        chunks      INT NOT NULL DEFAULT 0,
        size_bytes  INT NOT NULL DEFAULT 0,
        status      VARCHAR(20) NOT NULL DEFAULT 'indexed',
        uploaded_by VARCHAR(255),
        uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


# Columns added after the initial release. `CREATE TABLE IF NOT EXISTS` never
# touches an existing table, so new columns are applied here instead — each is
# checked first, making startup migration idempotent.
COLUMN_MIGRATIONS = [
    ("users", "is_active", "ALTER TABLE users ADD COLUMN is_active TINYINT NOT NULL DEFAULT 1"),
]

# Type changes for databases created before a column's definition changed.
# (table, column, expected DATA_TYPE, statement applied when it differs)
TYPE_MIGRATIONS = [
    ("users", "employee_id", "varchar",
     "ALTER TABLE users MODIFY COLUMN employee_id VARCHAR(20)"),
    ("invites", "employee_id", "varchar",
     "ALTER TABLE invites MODIFY COLUMN employee_id VARCHAR(20) NOT NULL"),
]

# Indexes the audit log needs once it grows past a few thousand rows.
INDEX_MIGRATIONS = [
    ("audit_log", "idx_audit_created", "ALTER TABLE audit_log ADD INDEX idx_audit_created (created_at)"),
    ("audit_log", "idx_audit_action", "ALTER TABLE audit_log ADD INDEX idx_audit_action (action)"),
]


def _apply_migrations(cur) -> None:
    for table, column, statement in COLUMN_MIGRATIONS:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            (table, column),
        )
        if cur.fetchone()[0] == 0:
            cur.execute(statement)
    for table, column, expected_type, statement in TYPE_MIGRATIONS:
        cur.execute(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            (table, column),
        )
        row = cur.fetchone()
        if row and row[0].lower() != expected_type:
            cur.execute(statement)
    for table, index, statement in INDEX_MIGRATIONS:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = %s AND INDEX_NAME = %s",
            (table, index),
        )
        if cur.fetchone()[0] == 0:
            cur.execute(statement)


def _pool() -> pooling.MySQLConnectionPool:
    global _POOL
    if _POOL is None:
        _POOL = pooling.MySQLConnectionPool(
            pool_name="orbis_app",
            pool_size=16,
            pool_reset_session=True,
            **settings.get_app_mysql_config(),
        )
    return _POOL


@contextmanager
def get_conn() -> Iterator[mysql.connector.MySQLConnection]:
    """Hand out a pooled connection. A single request runs several queries, so
    reusing connections avoids a connect/teardown per query."""
    try:
        conn = _pool().get_connection()
    except mysql.connector.Error:
        # Pool exhausted under a burst — degrade to a direct connection rather
        # than failing the request outright.
        conn = mysql.connector.connect(**settings.get_app_mysql_config(), connection_timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()  # pooled connections are returned, not torn down


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        for statement in SCHEMA:
            cur.execute(statement)
        _apply_migrations(cur)
        cur.close()


def query_one(sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row


def query_all(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Run an INSERT/UPDATE/DELETE; return lastrowid for inserts."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        last_id = cur.lastrowid
        cur.close()
        return last_id
