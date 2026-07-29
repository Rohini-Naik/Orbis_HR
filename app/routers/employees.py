"""Employee management endpoints (admin only) — manage HR `employees` rows."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.schemas import Employee, EmployeeCreate, EmployeeListResponse
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["employees"])

MAX_PAGE = 200  # hard ceiling so a single request cannot pull the whole table


@router.post("", response_model=Employee, status_code=201)
def create_employee(
    body: EmployeeCreate, admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    return employee_service.create(body.model_dump(exclude_none=True), admin)


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0),
    include_exited: bool = False,
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    return employee_service.list_employees(
        search=search, limit=limit, offset=offset, include_exited=include_exited
    )


@router.get("/{employee_id}", response_model=Employee)
def get_employee(employee_id: str, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return employee_service.get(employee_id)


@router.put("/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: str, body: EmployeeCreate, admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    return employee_service.update(employee_id, body.model_dump(exclude_none=True), admin)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: str, admin: Dict[str, Any] = Depends(require_admin)) -> None:
    """Mark the employee as exited and revoke their access. Not a hard delete."""
    employee_service.delete(employee_id, admin)


@router.post("/{employee_id}/reinstate", response_model=Employee)
def reinstate_employee(
    employee_id: str, admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    return employee_service.reinstate(employee_id, admin)
