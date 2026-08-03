"""Password resets.

A reset link takes over an existing account, so it is treated more carefully
than an onboarding invitation: it lives for an hour rather than a week, and
completing one signs the account out everywhere — if the reset was prompted by
a suspected compromise, leaving the attacker's session alive would defeat it.
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import HTTPException, status

from app.auth import hash_password, revoke_user_sessions
from app.db import execute, query_one
from app.services import audit_service, mailer
from rag_engine import settings

logger = logging.getLogger("orbis.password")

RESET_INVALID = "This reset link is invalid, has expired, or has already been used."

# Deliberately identical whether or not the address exists. Saying "no such
# account" would let anyone test which addresses are real.
RESET_SENT = (
    "If that address belongs to an Orbis account, a reset link is on its way. "
    "The link expires in {minutes} minutes."
)


def request_reset(email: str) -> str:
    """Start a reset. The response never reveals whether the account exists."""
    message = RESET_SENT.format(minutes=settings.RESET_TTL_MINUTES)
    user = query_one(
        "SELECT id, email, full_name, is_active FROM users WHERE email = %s", (email,)
    )
    if user is None or not user["is_active"]:
        logger.info("Password reset requested for an unknown or inactive address")
        return message

    # One live link at a time: a new request retires any previous one.
    execute(
        "UPDATE password_resets SET used_at = NOW() "
        "WHERE user_id = %s AND used_at IS NULL",
        (user["id"],),
    )
    token = secrets.token_urlsafe(32)
    execute(
        "INSERT INTO password_resets (token, user_id, expires_at) VALUES (%s, %s, %s)",
        (token, user["id"],
         datetime.now() + timedelta(minutes=settings.RESET_TTL_MINUTES)),
    )
    mailer.send_password_reset(
        user["email"], user["full_name"], f"{settings.APP_BASE_URL}/?reset={token}"
    )
    audit_service.log_event("password", user=user, question="Requested a password reset")
    return message


def _live_reset(token: str) -> Dict[str, Any]:
    row = query_one(
        "SELECT r.token, r.user_id, u.email, u.full_name "
        "FROM password_resets r JOIN users u ON u.id = r.user_id "
        "WHERE r.token = %s AND r.used_at IS NULL AND r.expires_at > NOW() "
        "AND u.is_active = 1",
        (token,),
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, RESET_INVALID)
    return row


def peek_reset(token: str) -> Dict[str, Any]:
    """Whose account a link belongs to, for the set-password screen."""
    row = _live_reset(token)
    return {"email": row["email"], "full_name": row["full_name"]}


def complete_reset(token: str, password: str) -> Dict[str, Any]:
    row = _live_reset(token)
    execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(password), row["user_id"]),
    )
    execute("UPDATE password_resets SET used_at = NOW() WHERE token = %s", (token,))
    # Every existing session is now suspect, including any the person did not
    # open themselves.
    revoke_user_sessions(row["user_id"])
    audit_service.log_event(
        "password",
        user={"id": row["user_id"], "email": row["email"],
              "full_name": row["full_name"], "role": "employee"},
        question="Completed a password reset",
    )
    return {"email": row["email"], "full_name": row["full_name"]}


def change_password(user: Dict[str, Any], current: str, new: str) -> None:
    """Change the password of the signed-in account."""
    from app.auth import verify_password

    row = query_one("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    if row is None or not verify_password(current, row["password_hash"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password is incorrect.")
    execute("UPDATE users SET password_hash = %s WHERE id = %s",
            (hash_password(new), user["id"]))
    revoke_user_sessions(user["id"])
    audit_service.log_event("password", user=user, question="Changed their password")
