"""Authentication: password hashing, opaque bearer tokens, and the FastAPI
dependencies that resolve the current user and enforce the admin role.
"""
import os
import secrets
from typing import Any, Dict

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import execute, query_one
from app.services import hr_identity_service

bearer_scheme = HTTPBearer(auto_error=False)

BCRYPT_MAX_BYTES = 72  # bcrypt's hard input limit; longer input raises
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "7"))
ACCOUNT_LINK_INVALID = (
    "This account is not linked to an active HR record. Please contact HR."
)


def _pw_bytes(password: str) -> bytes:
    """Clip to bcrypt's 72-byte limit — applied on both hash and verify so the
    two always agree."""
    return password.encode()[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_pw_bytes(password), password_hash.encode())


def revoke_token(token: str) -> None:
    execute("DELETE FROM sessions WHERE token = %s", (token,))


def revoke_user_sessions(user_id: int) -> None:
    """Sign a user out everywhere — used when an account is deactivated."""
    execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def create_token() -> str:
    return secrets.token_urlsafe(32)


def require_valid_hr_identity(user: Dict[str, Any]) -> None:
    """Fail closed unless the account has a current authoritative HR identity."""
    if not hr_identity_service.validate_account(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACCOUNT_LINK_INVALID)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    # Sessions expire on age (uses the existing created_at column — no migration).
    row = query_one(
        "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id "
        "WHERE s.token = %s AND s.created_at > NOW() - INTERVAL %s DAY",
        (creds.credentials, SESSION_TTL_DAYS),
    )
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if not row.get("is_active", 1):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    # App state alone is insufficient: an HR row may have been deleted, exited,
    # or reassigned while an older bearer token is still live.
    require_valid_hr_identity(row)
    return row


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
