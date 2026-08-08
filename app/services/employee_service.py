"""Admin employee management — create/list/update/delete rows in the HR
`employees` table via a dedicated read-write connection. The NL->SQL engine
keeps using the read-only user, so this write access never reaches the LLM path.
"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

import mysql.connector
from fastapi import HTTPException, status

from app.db import execute, get_conn, query_one
from app.services import audit_service
from app.services.identity import generate_email
from rag_engine import settings

COLUMNS = [
    "EmployeeID", "FullName", "Email", "PersonalEmail", "Role", "Department",
    "Location", "DateOfJoining", "ManagerID", "ManagerName",
    "CasualLeaveBalance", "CasualLeaveUsed", "SickLeaveBalance", "SickLeaveUsed",
    "EarnedLeaveBalance", "EarnedLeaveUsed", "LastAppraisalDate",
    "NextAppraisalDate", "POSHTrainingCompleted", "POSHTrainingDate",
    "PerformanceRating", "AnnualCTC_INR", "EmploymentType", "IsAdmin", "Status",
]

# `Email` is minted by the server and `Status` is managed by the lifecycle
# helpers, so neither is accepted from a request body. `IsAdmin` is HR reference
# data only — application permissions live on the users table, granted through
# "Users & Access", never by editing an employee record.
SERVER_MANAGED = {"Email", "Status", "IsAdmin"}

logger = logging.getLogger("orbis.employees")


@contextmanager
def _conn() -> Iterator[mysql.connector.MySQLConnection]:
    conn = mysql.connector.connect(**settings.get_hr_admin_mysql_config(), connection_timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


ID_PREFIX = "EMP"


def _next_employee_id(cur) -> str:
    """Allocate the next 'EMP####' id.

    IDs are never reused — including ones freed by an exit — because a recycled
    id would silently hand a departed colleague's account access to whoever
    inherits the number. MAX() over every row, exited included, guarantees that.
    """
    cur.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(EmployeeID, %s) AS UNSIGNED)), 1000) "
        "FROM employees WHERE EmployeeID LIKE %s",
        (len(ID_PREFIX) + 1, f"{ID_PREFIX}%"),
    )
    return f"{ID_PREFIX}{cur.fetchone()[0] + 1}"


def create(data: Dict[str, Any], admin: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new hire: allocate an ID, mint their company address, and invite
    them to set a password via their personal inbox."""
    payload = {k: v for k, v in data.items() if k not in SERVER_MANAGED}
    personal_email = payload.get("PersonalEmail")

    # Every statement here is covered: an id lookup or the uniqueness probe can
    # fail just as the insert can, and an escaping driver error would reach the
    # browser as an opaque network failure rather than a usable message.
    try:
        with _conn() as conn:
            cur = conn.cursor()
            if payload.get("EmployeeID"):
                cur.execute("SELECT 1 FROM employees WHERE EmployeeID = %s",
                            (payload["EmployeeID"],))
                if cur.fetchone():
                    raise HTTPException(status.HTTP_409_CONFLICT, "EmployeeID already exists")
            else:
                payload["EmployeeID"] = _next_employee_id(cur)

            def taken(candidate: str) -> bool:
                cur.execute("SELECT 1 FROM employees WHERE Email = %s", (candidate,))
                return cur.fetchone() is not None

            payload["Email"] = generate_email(payload.get("FullName", ""), is_taken=taken)
            payload["Status"] = "active"

            cols = [c for c in COLUMNS if c in payload]
            cur.execute(
                f"INSERT INTO employees ({', '.join(cols)}) "
                f"VALUES ({', '.join(['%s'] * len(cols))})",
                [payload[c] for c in cols],
            )
            cur.close()
    except mysql.connector.Error as exc:
        # Never surface the driver's message: it leaks schema details.
        logger.exception("Employee create failed")
        detail = "Could not create the employee record. Please check the submitted values."
        if exc.errno == 1054:  # unknown column — the HR table predates this build
            detail = ("The employee table is out of date. Re-run setup to apply the "
                      "current schema.")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)

    from app.services import onboarding_service  # local import avoids a cycle

    onboarding_service.issue_invite(
        payload["EmployeeID"], payload["Email"],
        payload.get("FullName", ""), personal_email,
    )
    audit_service.log_event(
        "employee", user=admin,
        question=f"Added employee {payload['EmployeeID']} ({payload['Email']})",
    )
    return get(payload["EmployeeID"])


def list_employees(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_exited: bool = False,
) -> Dict[str, Any]:
    clauses, params = [], []
    if not include_exited:
        clauses.append("Status = 'active'")
    if search:
        clauses.append("(FullName LIKE %s OR Department LIKE %s OR Role LIKE %s OR Email LIKE %s)")
        params += [f"%{search}%"] * 4
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(f"SELECT COUNT(*) AS n FROM employees {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT * FROM employees {where} ORDER BY EmployeeID LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = cur.fetchall()
        cur.close()
    return {"total": total, "employees": rows}


def get(employee_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM employees WHERE EmployeeID = %s", (employee_id,))
        row = cur.fetchone()
        cur.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    return row


def update(employee_id: str, data: Dict[str, Any], admin: Dict[str, Any]) -> Dict[str, Any]:
    data = {k: v for k, v in data.items() if k not in SERVER_MANAGED}
    fields = [c for c in COLUMNS if c in data and c != "EmployeeID"]
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    assignments = ", ".join(f"{c} = %s" for c in fields)
    values = [data[c] for c in fields] + [employee_id]
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE employees SET {assignments} WHERE EmployeeID = %s", values)
        affected = cur.rowcount
        cur.close()
    if affected == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    audit_service.log_event("employee", user=admin, question=f"Updated employee {employee_id}")
    return get(employee_id)


def delete(employee_id: str, admin: Dict[str, Any]) -> None:
    """Mark an employee as exited.

    Records are never removed: the audit trail references them, and a deleted
    row whose ID was later reissued would give the new holder access to the
    previous employee's account. Deactivating the linked login and dropping its
    sessions ends access immediately.
    """
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE employees SET Status = 'exited' WHERE EmployeeID = %s AND Status <> 'exited'",
            (employee_id,),
        )
        affected = cur.rowcount
        cur.close()
    if affected == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found or already exited")

    # employee_id is not unique on legacy users tables, so deactivate every
    # linked account rather than silently revoking only whichever row
    # ``query_one`` happened to return. Keep the account update and session
    # cleanup in one app-database transaction.
    with get_conn() as app_conn:
        app_cur = app_conn.cursor()
        app_cur.execute(
            "UPDATE users SET is_active = 0 WHERE employee_id = %s",
            (employee_id,),
        )
        app_cur.execute(
            "DELETE s FROM sessions s "
            "INNER JOIN users u ON u.id = s.user_id "
            "WHERE u.employee_id = %s",
            (employee_id,),
        )
        app_cur.close()
    execute("UPDATE invites SET used_at = NOW() WHERE employee_id = %s AND used_at IS NULL",
            (employee_id,))
    audit_service.log_event(
        "employee", user=admin,
        question=f"Marked employee {employee_id} as exited and revoked access",
    )


def reinstate(employee_id: str, admin: Dict[str, Any]) -> Dict[str, Any]:
    """Undo an exit — the counterpart that hard deletion could never offer."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE employees SET Status = 'active' WHERE EmployeeID = %s", (employee_id,))
        affected = cur.rowcount
        cur.close()
    if affected == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    record = get(employee_id)
    # Legacy data may contain multiple accounts with the same employee_id.
    # Reactivate only the account whose company email still matches the
    # authoritative HR identity; never pick an arbitrary duplicate.
    linked = query_one(
        "SELECT id FROM users WHERE employee_id = %s AND email = %s",
        (employee_id, record.get("Email")),
    )
    if linked:
        execute("UPDATE users SET is_active = 1 WHERE id = %s", (linked["id"],))
    audit_service.log_event("employee", user=admin, question=f"Reinstated employee {employee_id}")
    return record
