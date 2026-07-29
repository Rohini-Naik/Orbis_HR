"""User administration (admin only): view accounts and grant or revoke admin
rights — how a newly joined HR colleague is given access to the app."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_admin, revoke_user_sessions
from app.db import execute, query_all, query_one
from app.schemas import RoleUpdateRequest, UserSummary
from app.services import audit_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserSummary])
def list_users(admin: Dict[str, Any] = Depends(require_admin)) -> List[Dict[str, Any]]:
    return query_all(
        "SELECT id, email, full_name, role, employee_id, department, is_active, created_at "
        "FROM users ORDER BY role, full_name"
    )


@router.put("/{user_id}/role", response_model=UserSummary)
def set_role(
    user_id: int,
    body: RoleUpdateRequest,
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Promote a colleague to HR admin, or revoke that access.

    Two guardrails matter here: an admin demoting themselves would lose the
    ability to undo it, and demoting the final admin would leave the app with
    nobody able to administer it at all.
    """
    user = query_one("SELECT id, email, role FROM users WHERE id = %s", (user_id,))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.role != "admin":
        if user["id"] == admin["id"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You cannot revoke your own admin access"
            )
        remaining = query_one(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1"
        )["n"]
        if user["role"] == "admin" and remaining <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "At least one administrator must remain"
            )

    if user["role"] != body.role:
        execute("UPDATE users SET role = %s WHERE id = %s", (body.role, user_id))
        # Force a fresh sign-in so the new permissions are picked up cleanly.
        revoke_user_sessions(user_id)
        audit_service.log_event(
            "role", user=admin,
            question=f"Set {user['email']} role to '{body.role}'",
        )
    return query_one(
        "SELECT id, email, full_name, role, employee_id, department, is_active, created_at "
        "FROM users WHERE id = %s",
        (user_id,),
    )
