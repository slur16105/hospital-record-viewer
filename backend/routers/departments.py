from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError as PostgrestAPIError

from core.auth import get_current_user
from core.database import get_supabase_for_user
from models.departments import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["departments"])


def _check_duplicate_name(client, name: str, exclude_id: str | None = None) -> None:
    """Raises 409 if name already exists. Provides hint when existing dept is inactive."""
    query = client.table("departments").select("id, is_active").eq("name", name)
    if exclude_id:
        query = query.neq("id", exclude_id)
    result = query.execute()
    if result.data:
        if result.data[0].get("is_active"):
            raise HTTPException(status_code=409, detail="이미 존재하는 진료과목 이름입니다")
        raise HTTPException(
            status_code=409,
            detail="이미 존재하는 진료과목 이름입니다 (현재 비활성 상태). 기존 진료과목을 활성화하여 사용하세요.",
        )


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[DepartmentOut]:
    client = get_supabase_for_user(current_user["token"])
    result = client.table("departments").select("id, name, is_active").order("name").execute()
    return result.data or []


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DepartmentOut:
    client = get_supabase_for_user(current_user["token"])
    _check_duplicate_name(client, body.name)
    try:
        result = client.table("departments").insert({"name": body.name}).execute()
    except PostgrestAPIError as e:
        if e.code == "23505":
            raise HTTPException(status_code=409, detail="이미 존재하는 진료과목 이름입니다")
        raise HTTPException(status_code=500, detail="저장 중 오류가 발생했습니다")
    if not result.data:
        raise HTTPException(status_code=403, detail="저장 권한이 없습니다")
    return result.data[0]


@router.patch("/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: UUID,
    body: DepartmentUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DepartmentOut:
    client = get_supabase_for_user(current_user["token"])
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")
    if "name" in update_data:
        _check_duplicate_name(client, update_data["name"], exclude_id=str(dept_id))
    try:
        result = (
            client.table("departments").update(update_data).eq("id", str(dept_id)).execute()
        )
    except PostgrestAPIError as e:
        if e.code == "23505":
            raise HTTPException(status_code=409, detail="이미 존재하는 진료과목 이름입니다")
        raise HTTPException(status_code=500, detail="수정 중 오류가 발생했습니다")
    if not result.data:
        raise HTTPException(status_code=404, detail="Not found")
    return result.data[0]
