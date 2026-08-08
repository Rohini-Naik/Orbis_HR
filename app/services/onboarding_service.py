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

from fastapi import HTTPException, status

from app.auth import hash_password
from app.db import execute, query_one
from app.services import audit_service, hr_identity_service, mailer
from rag_engine import settings

NOT_ON_RECORD = (
    "That email address isn't in our HR records. "
    "If you have just joined, please contact HR to get set up."
)
ALREADY_REGISTERED = "An account already exists for that address. Please sign in."
INVITE_INVALID = "This invitation link is invalid, has expired, or has already been used."


def _create_user(email: str, password: str, full_name: str,
                 employee_id: Optional[str], department: Optional[str]) -> int:
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

    record = hr_identity_service.get_by_identity(
        invite["employee_id"], invite["company_email"]
    )
    if not hr_identity_service.is_active(record):
        # Retire every copy for this address. A missing, reassigned, or exited HR
        # identity must never be able to create an account later.
        execute(
            "UPDATE invites SET used_at = NOW() "
            "WHERE company_email = %s AND used_at IS NULL",
            (invite["company_email"],),
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVITE_INVALID)
    user_id = _create_user(
        record["Email"], password, record["FullName"],
        record["EmployeeID"], record.get("Department"),
    )
    # Single use: burn the token, and retire any other outstanding invite for
    # the same address so a reissued link cannot create a second account.
    execute("UPDATE invites SET used_at = NOW() WHERE company_email = %s AND used_at IS NULL",
            (invite["company_email"],))
    audit_service.log_event("onboarding", user={"id": user_id, "full_name": record["FullName"],
                                                "email": record["Email"], "role": "employee"},
                            question="Accepted invitation")
    return {"id": user_id, "email": record["Email"],
            "full_name": record["FullName"], "role": "employee"}


# -------------------------------------------------------------- self-service
def self_register(company_email: str, password: str) -> Dict[str, Any]:
    """Register using a company address already present in the HR system."""
    if query_one("SELECT id FROM users WHERE email = %s", (company_email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_REGISTERED)

    record = hr_identity_service.get_by_email(company_email)
    if not hr_identity_service.is_active(record):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_ON_RECORD)

    user_id = _create_user(
        record["Email"], password, record["FullName"],
        record["EmployeeID"], record.get("Department"),
    )
    audit_service.log_event("onboarding", user={"id": user_id, "full_name": record["FullName"],
                                                "email": record["Email"], "role": "employee"},
                            question="Self-registered")
    return {"id": user_id, "email": record["Email"],
            "full_name": record["FullName"], "role": "employee"}
