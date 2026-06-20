"""Audit trail: record every AI response, file change and hallucination block,
and expose the log + stats for the admin (incl. CSV export)."""
import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.db import execute, query_all, query_one


def log_event(
    action: str,
    user: Optional[Dict[str, Any]] = None,
    question: Optional[str] = None,
    route: Optional[str] = None,
    sql: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    confidence: Optional[float] = None,
    latency_ms: Optional[int] = None,
    hallucination_blocked: bool = False,
) -> None:
    execute(
        "INSERT INTO audit_log (user_id, username, role, action, question, route, "
        "sql_text, sources, confidence, latency_ms, hallucination_blocked) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            (user or {}).get("id"),
            (user or {}).get("full_name") or (user or {}).get("email"),
            (user or {}).get("role"),
            action,
            question,
            route,
            sql,
            json.dumps(sources) if sources is not None else None,
            confidence,
            latency_ms,
            int(hallucination_blocked),
        ),
    )


def _status(entry: Dict[str, Any]) -> str:
    if entry["hallucination_blocked"]:
        return "Blocked"
    if entry["action"] in ("upload", "delete", "employee"):
        return "Complete"
    return "Verified"


def list_entries(limit: int = 200) -> List[Dict[str, Any]]:
    rows = query_all(
        "SELECT id, user_id, username, role, action, question, route, "
        "sql_text AS `sql`, confidence, latency_ms, hallucination_blocked, created_at "
        "FROM audit_log ORDER BY id DESC LIMIT %s",
        (limit,),
    )
    for row in rows:
        row["status"] = _status(row)
        _redact(row)
    return rows


def _redact(row: Dict[str, Any]) -> None:
    """Privacy: an employee's actual question/SQL is personal content. Admins
    only need it for BLOCKED entries they must investigate; for normal chat
    activity we expose metadata only (who/when/route/status)."""
    if row["action"] == "chat" and not row["hallucination_blocked"]:
        row["question"] = None
        row["sql"] = None


def count_queries() -> int:
    return query_one("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'chat'")["n"]


def accuracy_rate() -> float:
    """Share of answered chat queries that passed the hallucination filter."""
    row = query_one(
        "SELECT COUNT(*) AS total, COALESCE(SUM(hallucination_blocked), 0) AS blocked "
        "FROM audit_log WHERE action = 'chat'"
    )
    total, blocked = row["total"] or 0, row["blocked"] or 0
    return round((total - blocked) / total, 3) if total else 1.0


def stats() -> Dict[str, Any]:
    today = query_one(
        "SELECT COUNT(*) AS n FROM audit_log WHERE DATE(created_at) = CURDATE()"
    )["n"]
    flagged = query_one(
        "SELECT COUNT(*) AS n FROM audit_log WHERE hallucination_blocked = 1"
    )["n"]
    avg = query_one(
        "SELECT AVG(latency_ms) AS a FROM audit_log WHERE action = 'chat'"
    )["a"]
    return {
        "events_today": today,
        "flagged_for_review": flagged,
        "avg_response_ms": int(avg) if avg is not None else None,
        "verification_pass_rate": accuracy_rate(),
    }


def export_csv() -> str:
    entries = list_entries(limit=100000)
    buffer = io.StringIO()
    fields = [
        "id", "created_at", "username", "role", "action", "question",
        "route", "sql", "confidence", "latency_ms", "hallucination_blocked", "status",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(entries)
    return buffer.getvalue()
