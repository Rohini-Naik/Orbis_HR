"""Application-state storage (MySQL).

Holds everything the app itself owns — users, sessions, conversations,
messages, the audit trail and policy-file metadata — in the read-write
`orbis_app` database. The HR employee data lives separately in `orbis_hr`
and is only ever read through the read-only `orbis_user`.
"""
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence

import mysql.connector

from rag_engine import settings

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        email         VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name     VARCHAR(255) NOT NULL,
        role          VARCHAR(20) NOT NULL,
        employee_id   INT,
        department    VARCHAR(100),
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


@contextmanager
def get_conn() -> Iterator[mysql.connector.MySQLConnection]:
    conn = mysql.connector.connect(**settings.get_app_mysql_config(), connection_timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        for statement in SCHEMA:
            cur.execute(statement)
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
