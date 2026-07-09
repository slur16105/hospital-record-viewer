from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError as PostgrestAPIError

from core.authz import require_permission
from core.database import get_supabase_admin
from core.permissions import P
from models.rooms import RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/rooms", tags=["rooms"])

_ROOM_SELECT = "id, room_number, department_id, is_active, departments(name)"


def _flatten_room(row: dict) -> dict:
    return {
        "id": row["id"],
        "room_number": row["room_number"],
        "department_id": row["department_id"],
        "department_name": row.get("departments", {}).get("name", ""),
        "is_active": row["is_active"],
    }


def _check_duplicate(client, room_number: str, department_id: str, exclude_id: str | None = None) -> None:
    query = (
        client.table("examination_rooms")
        .select("id")
        .eq("room_number", room_number)
        .eq("department_id", department_id)
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    result = query.execute()
    if result.data:
        raise HTTPException(
            status_code=409, detail="해당 진료과목에 이미 존재하는 진료실 번호입니다"
        )


@router.get("", response_model=list[RoomOut])
def list_rooms(
    current_user: Annotated[dict, Depends(require_permission(P.DEPARTMENTS_READ))],
) -> list[RoomOut]:
    client = get_supabase_admin()
    result = (
        client.table("examination_rooms")
        .select(_ROOM_SELECT)
        .order("room_number")
        .execute()
    )
    return [_flatten_room(r) for r in (result.data or [])]


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    body: RoomCreate,
    current_user: Annotated[dict, Depends(require_permission(P.DEPARTMENTS_MANAGE))],
) -> RoomOut:
    client = get_supabase_admin()
    _check_duplicate(client, body.room_number, str(body.department_id))
    try:
        result = (
            client.table("examination_rooms")
            .insert({"room_number": body.room_number, "department_id": str(body.department_id)})
            .select(_ROOM_SELECT)
            .execute()
        )
    except PostgrestAPIError as e:
        if e.code == "23505":
            raise HTTPException(status_code=409, detail="해당 진료과목에 이미 존재하는 진료실 번호입니다")
        raise HTTPException(status_code=500, detail="저장 중 오류가 발생했습니다")
    if not result.data:
        raise HTTPException(status_code=403, detail="저장 권한이 없습니다")
    return _flatten_room(result.data[0])


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(
    room_id: UUID,
    body: RoomUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.DEPARTMENTS_MANAGE))],
) -> RoomOut:
    client = get_supabase_admin()
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")

    if "department_id" in update_data:
        update_data["department_id"] = str(update_data["department_id"])

    if "room_number" in update_data or "department_id" in update_data:
        existing = (
            client.table("examination_rooms")
            .select("room_number, department_id")
            .eq("id", str(room_id))
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Not found")
        current = existing.data[0]
        check_number = update_data.get("room_number", current["room_number"])
        check_dept = update_data.get("department_id", current["department_id"])
        _check_duplicate(client, check_number, check_dept, exclude_id=str(room_id))

    try:
        result = (
            client.table("examination_rooms")
            .update(update_data)
            .eq("id", str(room_id))
            .select(_ROOM_SELECT)
            .execute()
        )
    except PostgrestAPIError as e:
        if e.code == "23505":
            raise HTTPException(status_code=409, detail="해당 진료과목에 이미 존재하는 진료실 번호입니다")
        raise HTTPException(status_code=500, detail="수정 중 오류가 발생했습니다")
    if not result.data:
        raise HTTPException(status_code=404, detail="Not found")
    return _flatten_room(result.data[0])
