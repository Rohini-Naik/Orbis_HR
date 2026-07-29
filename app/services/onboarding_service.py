"""Account onboarding.

Two ways to get an account, both anchored on the company email address held in
the HR record — the client never supplies its own `employee_id`:

* **Invited** — HR adds a new hire, the system mints their company address and
  emails a single-use link to their personal inbox. Only the holder of that
  inbox can activate the account.
* **Self-service** — staff already in the HR system (bulk-loaded, so no personal
  address on file) register with the company address HR gave them.
"""
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import mysql.connector
from fastapi import HTTPException, status

from app.auth import hash_password
from app.db import execute, query_one
from app.services import audit_service, mailer
from rag_engine import settings

NOT_ON_RECORD = (
    "That email address isn't in our HR records. "
    "If you have just joined, please contact HR to get set up."
)
ALREADY_REGISTERED = "An account already exists for that address. Please sign in."
INVITE_INVALID = "This invitation link is invalid, has expired, or has already been used."


def _hr_lookup(email: str) -> Optional[Dict[str, Any]]:
    """Read-only HR lookup by company email."""
    conn = mysql.connector.connect(**settings.get_mysql_config(), connection_timeout=10)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT EmployeeID, FullName, Department, Status FROM employees WHERE Email = %s",
            (email,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _create_user(email: str, password: str, full_name: str,
                 employee_id: Optional[int], department: Optional[str]) -> int:
    return execute(
        "INSERT INTO users (email, password_hash, full_name, role, employee_id, department) "
        "VALUES (%s, %s, %s, 'employee', %s, %s)",
        (email, hash_password(password), full_name, employee_id, department),
    )


# ------------------------------------------------------------------- invites
def issue_invite(employee_id: str, company_email: str, full_name: str,
                 personal_email: Optional[str]) -> Optional[str]:
    """Record an invitation and email the link. Returns the token so the caller
    can surface it when no mail backend is configured."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(days=settings.INVITE_TTL_DAYS)
    execute(
        "INSERT INTO invites (token, employee_id, company_email, full_name, expires_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (token, employee_id, company_email, full_name, expires),
    )
    if personal_email:
        link = f"{settings.APP_BASE_URL}/?invite={token}"
        mailer.send_invite(personal_email, full_name, company_email, link)
    return token


def peek_invite(token: str) -> Dict[str, Any]:
    """Details for the set-password screen, without consuming the invite."""
    row = query_one(
        "SELECT company_email, full_name FROM invites "
        "WHERE token = %s AND used_at IS NULL AND expires_at > NOW()",
        (token,),
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVITE_INVALID)
    return row


def accept_invite(token: str, password: str) -> Dict[str, Any]:
    invite = query_one(
        "SELECT * FROM invites WHERE token = %s AND used_at IS NULL AND expires_at > NOW()",
        (token,),
    )
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVITE_INVALID)
    if query_one("SELECT id FROM users WHERE email = %s", (invite["company_email"],)):
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_REGISTERED)

    record = _hr_lookup(invite["company_email"])
    user_id = _create_user(
        invite["company_email"], password, invite["full_name"],
        invite["employee_id"], (record or {}).get("Department"),
    )
    # Single use: burn the token, and retire any other outstanding invite for
    # the same address so a reissued link cannot create a second account.
    execute("UPDATE invites SET used_at = NOW() WHERE company_email = %s AND used_at IS NULL",
            (invite["company_email"],))
    audit_service.log_event("onboarding", user={"id": user_id, "full_name": invite["full_name"],
                                                "email": invite["company_email"], "role": "employee"},
                            question="Accepted invitation")
    return {"id": user_id, "email": invite["company_email"],
            "full_name": invite["full_name"], "role": "employee"}


# -------------------------------------------------------------- self-service
def self_register(company_email: str, password: str) -> Dict[str, Any]:
    """Register using a company address already present in the HR system."""
    if query_one("SELECT id FROM users WHERE email = %s", (company_email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_REGISTERED)

    record = _hr_lookup(company_email)
    if record is None or record.get("Status") == "exited":
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_ON_RECORD)

    user_id = _create_user(
        company_email, password, record["FullName"],
        record["EmployeeID"], record.get("Department"),
    )
    audit_service.log_event("onboarding", user={"id": user_id, "full_name": record["FullName"],
                                                "email": company_email, "role": "employee"},
                            question="Self-registered")
    return {"id": user_id, "email": company_email,
            "full_name": record["FullName"], "role": "employee"}
