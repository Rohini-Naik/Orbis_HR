"""Audit log endpoints (admin only)."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Response

from app.auth import require_admin
from app.schemas import AuditEntry, AuditStats
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[AuditEntry])
def list_audit(
    limit: int = 200, admin: Dict[str, Any] = Depends(require_admin)
) -> List[Dict[str, Any]]:
    return audit_service.list_entries(limit=limit)


@router.get("/stats", response_model=AuditStats)
def audit_stats(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return audit_service.stats()


@router.get("/export")
def export_audit(admin: Dict[str, Any] = Depends(require_admin)) -> Response:
    return Response(
        content=audit_service.export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
