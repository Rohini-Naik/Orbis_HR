"""Read-only HR identity checks shared by authentication and administration.

The application database says which account is signing in; the HR database is
the authority for whether a linked employee identity still exists and is active.
Keeping that decision here prevents login, bearer-token authentication, and
onboarding from drifting into subtly different rules.
"""
import logging
from typing import Any, Dict, Iterable, Optional

import mysql.connector
from fastapi import HTTPException, status

from rag_engine import settings


logger = logging.getLogger("orbis.hr_identity")

HR_DIRECTORY_UNAVAILABLE = (
    "HR records are temporarily unavailable. Please try again shortly."
)


def normalise_employee_id(value: Any) -> str:
    """Canonical comparison key for employee identifiers from either database."""
    return str(value or "").strip().casefold()


def is_active(record: Optional[Dict[str, Any]]) -> bool:
    return bool(record) and str(record.get("Status") or "").strip().casefold() == "active"


def is_bootstrap_admin(user: Dict[str, Any]) -> bool:
    """The sole account type allowed without an HR employee identity.

    ``app.provision create-admin`` deliberately supports an operator-created
    administrator when no matching employee exists.  Requiring ``None`` rather
    than any false-ish value keeps malformed linked accounts from inheriting the
    exception.
    """
    return user.get("role") == "admin" and user.get("employee_id") is None


def _query_one(sql: str, params: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    try:
        conn = mysql.connector.connect(
            **settings.get_mysql_config(), connection_timeout=10
        )
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, params)
            row = cur.fetchone()
            cur.close()
            return row
        finally:
            conn.close()
    except mysql.connector.Error as exc:
        logger.exception("HR identity lookup failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            HR_DIRECTORY_UNAVAILABLE,
        ) from exc


def get_by_email(email: str) -> Optional[Dict[str, Any]]:
    return _query_one(
        "SELECT EmployeeID, FullName, Email, Department, Status "
        "FROM employees WHERE Email = %s",
        (email,),
    )


def get_by_identity(employee_id: Any, email: str) -> Optional[Dict[str, Any]]:
    """Return a record only when both immutable link fields identify one row."""
    if employee_id is None or not email:
        return None
    return _query_one(
        "SELECT EmployeeID, FullName, Email, Department, Status "
        "FROM employees WHERE EmployeeID = %s AND Email = %s",
        (employee_id, email),
    )


def get_by_employee_ids(employee_ids: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    """Bulk lookup for Users & Access without an N+1 database query."""
    ids = list(
        dict.fromkeys(
            str(value).strip()
            for value in employee_ids
            if value is not None and str(value).strip()
        )
    )
    if not ids:
        return {}
    placeholders = ", ".join(["%s"] * len(ids))
    try:
        conn = mysql.connector.connect(
            **settings.get_mysql_config(), connection_timeout=10
        )
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT EmployeeID, FullName, Email, Department, Status "
                f"FROM employees WHERE EmployeeID IN ({placeholders})",
                tuple(ids),
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()
    except mysql.connector.Error as exc:
        logger.exception("Bulk HR identity lookup failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            HR_DIRECTORY_UNAVAILABLE,
        ) from exc
    return {normalise_employee_id(row["EmployeeID"]): row for row in rows}


def validate_account(user: Dict[str, Any]) -> bool:
    """Whether an app account currently has authority to authenticate.

    Normal accounts require an exact EmployeeID + company-email match and an
    active HR lifecycle state.  The only unlinked exception is the deliberate
    bootstrap administrator created on the server.
    """
    if is_bootstrap_admin(user):
        return True
    employee_id, email = user.get("employee_id"), user.get("email")
    if employee_id is None or not email:
        return False
    return is_active(get_by_identity(employee_id, str(email)))
