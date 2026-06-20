"""Authentication endpoints: sign up, sign in, current user."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db import execute, query_one
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user_id: int) -> str:
    token = create_token()
    execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
    return token


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest) -> TokenResponse:
    """Register a normal user (role 'employee'). Admins are provisioned separately."""
    if query_one("SELECT id FROM users WHERE email = %s", (body.email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user_id = execute(
        "INSERT INTO users (email, password_hash, full_name, role, employee_id, department) "
        "VALUES (%s, %s, %s, 'employee', %s, %s)",
        (body.email, hash_password(body.password), body.full_name,
         body.employee_id, body.department),
    )
    return TokenResponse(
        access_token=_issue_token(user_id), email=body.email,
        full_name=body.full_name, role="employee",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    user = query_one("SELECT * FROM users WHERE email = %s", (body.email,))
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenResponse(
        access_token=_issue_token(user["id"]), email=user["email"],
        full_name=user["full_name"], role=user["role"],
    )


@router.get("/me", response_model=UserProfile)
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user
