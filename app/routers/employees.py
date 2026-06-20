"""Employee management endpoints (admin only) — manage HR `employees` rows."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.schemas import Employee, EmployeeCreate, EmployeeListResponse
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=Employee, status_code=201)
def create_employee(
    body: EmployeeCreate, admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    return employee_service.create(body.model_dump(exclude_none=True), admin)


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    return employee_service.list_employees(search=search, limit=limit, offset=offset)


@router.get("/{employee_id}", response_model=Employee)
def get_employee(employee_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return employee_service.get(employee_id)


@router.put("/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: int, body: EmployeeCreate, admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    return employee_service.update(employee_id, body.model_dump(exclude_none=True), admin)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> None:
    employee_service.delete(employee_id, admin)
