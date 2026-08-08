"""Authentication endpoints: onboarding, sign in, sign out, current user."""
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import (
    bearer_scheme,
    create_token,
    get_current_user,
    require_valid_hr_identity,
    revoke_token,
    verify_password,
)
from app.db import execute, query_one
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InviteAcceptRequest,
    InvitePreview,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    ResetPreview,
    SignupRequest,
    TokenResponse,
    UserProfile,
)
from app.services import onboarding_service, password_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Throttle credential guessing per email address. In-process and deliberately
# simple; a multi-worker deployment would move this to a shared store.
LOGIN_LIMIT = 8
LOGIN_WINDOW_S = 300
_attempts: Dict[str, Deque[float]] = defaultdict(deque)


def _check_login_rate(email: str) -> None:
    now = time.monotonic()
    hits = _attempts[email.lower()]
    while hits and now - hits[0] > LOGIN_WINDOW_S:
        hits.popleft()
    if len(hits) >= LOGIN_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Please try again in a few minutes.",
        )


def _record_failure(email: str) -> None:
    _attempts[email.lower()].append(time.monotonic())


def _issue_token(user_id: int) -> str:
    user = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if not user.get("is_active", 1):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account has been deactivated. Please contact HR.",
        )
    # Centralised here so login, signup, invite acceptance, password reset, and
    # password change can never create a session without the same HR check.
    require_valid_hr_identity(user)
    token = create_token()
    execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
    return token


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest) -> TokenResponse:
    """Self-registration for staff already on the HR system, using the company
    address HR issued them. Everything else is read from the HR record."""
    user = onboarding_service.self_register(body.email, body.password)
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.get("/invite/{token}", response_model=InvitePreview)
def preview_invite(token: str) -> Dict[str, Any]:
    """Show a new hire their company address before they set a password."""
    return onboarding_service.peek_invite(token)


@router.post("/invite/accept", response_model=TokenResponse, status_code=201)
def accept_invite(body: InviteAcceptRequest) -> TokenResponse:
    user = onboarding_service.accept_invite(body.token, body.password)
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    _check_login_rate(body.email)
    user = query_one("SELECT * FROM users WHERE email = %s", (body.email,))
    if user is None or not verify_password(body.password, user["password_hash"]):
        _record_failure(body.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.get("is_active", 1):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account has been deactivated. Please contact HR.",
        )
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest) -> Dict[str, str]:
    """Start a password reset. The reply is the same whether or not the address
    exists, so this cannot be used to discover who has an account."""
    _check_login_rate(body.email)
    _record_failure(body.email)  # count towards the same budget as sign-in attempts
    return {"message": password_service.request_reset(body.email)}


@router.get("/reset/{token}", response_model=ResetPreview)
def preview_reset(token: str) -> Dict[str, Any]:
    """Confirm which account a reset link belongs to before a password is set."""
    return password_service.peek_reset(token)


@router.post("/reset", response_model=TokenResponse, status_code=200)
def reset_password(body: ResetPasswordRequest) -> TokenResponse:
    """Set a new password and sign the person straight in."""
    account = password_service.complete_reset(body.token, body.password)
    user = query_one("SELECT * FROM users WHERE email = %s", (account["email"],))
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    body: ChangePasswordRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> TokenResponse:
    """Change the signed-in account's password. Other sessions are ended."""
    password_service.change_password(user, body.current_password, body.new_password)
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> None:
    """Invalidate the presented token server-side (idempotent)."""
    if creds is not None:
        revoke_token(creds.credentials)


@router.get("/me", response_model=UserProfile)
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user
