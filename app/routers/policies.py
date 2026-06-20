"""Policy Library endpoints (admin only)."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from app.auth import require_admin
from app.schemas import PolicyFile, PolicyStats
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", response_model=PolicyFile, status_code=201)
async def upload_policy(
    file: UploadFile = File(...), admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    content = await file.read()
    return policy_service.upload(file.filename, content, admin)


@router.get("", response_model=List[PolicyFile])
def list_policies(
    search: Optional[str] = None,
    category: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    return policy_service.list_files(search=search, category=category)


@router.get("/stats", response_model=PolicyStats)
def policy_stats(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return policy_service.stats()


@router.get("/{file_id}")
def view_policy(file_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return policy_service.get_file(file_id)


@router.get("/{file_id}/download")
def download_policy(file_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> FileResponse:
    path = policy_service.get_file_path(file_id)
    return FileResponse(path, filename=path.name)


@router.delete("/{file_id}", status_code=204)
def delete_policy(file_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> None:
    policy_service.delete(file_id, admin)
