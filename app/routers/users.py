"""User administration (admin only): view accounts and grant or revoke admin
rights — how a newly joined HR colleague is given access to the app."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_admin, revoke_user_sessions
from app.db import execute, query_all, query_one
from app.schemas import RoleUpdateRequest, UserSummary
from app.services import audit_service, hr_identity_service

router = APIRouter(prefix="/users", tags=["users"])

PROMOTION_CONFLICT = (
    "Admin access can only be granted to an active account linked to a matching "
    "active HR employee"
)


def _normalise_identity(value: Any) -> str:
    return str(value or "").strip().casefold()


def _matches_hr_identity(user: Dict[str, Any], employee: Dict[str, Any] | None) -> bool:
    """Whether an application account still names the same HR employee.

    Status is deliberately not considered here: Users & Access must retain a
    correctly linked exited account so an administrator can see and clean it
    up. Promotion applies the stricter active-status rule separately.
    """
    if employee is None or not user.get("employee_id"):
        return False
    return (
        _normalise_identity(user["employee_id"])
        == _normalise_identity(employee.get("EmployeeID"))
        and _normalise_identity(user.get("email"))
        == _normalise_identity(employee.get("Email"))
    )


@router.get("", response_model=List[UserSummary])
def list_users(admin: Dict[str, Any] = Depends(require_admin)) -> List[Dict[str, Any]]:
    users = query_all(
        "SELECT id, email, full_name, role, employee_id, department, is_active, created_at "
        "FROM users ORDER BY role, full_name"
    )
    employee_ids = [
        user["employee_id"] for user in users if user.get("employee_id") is not None
    ]
    employees = hr_identity_service.get_by_employee_ids(employee_ids)

    visible = []
    for user in users:
        if hr_identity_service.is_bootstrap_admin(user):
            visible.append(user)
            continue
        employee = employees.get(_normalise_identity(user.get("employee_id")))
        if _matches_hr_identity(user, employee):
            # The HR lifecycle is authoritative. If the cross-database account
            # update ever failed after an employee exited, do not present that
            # stale app row as active in Users & Access.
            visible_user = dict(user)
            if not hr_identity_service.is_active(employee):
                visible_user["is_active"] = False
            visible.append(visible_user)
    return visible


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
    user = query_one(
        "SELECT id, email, role, employee_id, is_active FROM users WHERE id = %s",
        (user_id,),
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.role == "admin":
        # Do this even for a no-op PUT on an existing admin: the endpoint must
        # never affirm an invalid/inactive identity as eligible for admin access.
        if not user.get("is_active") or not hr_identity_service.validate_account(user):
            raise HTTPException(status.HTTP_409_CONFLICT, PROMOTION_CONFLICT)
    else:
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
