"""역할·권한·필드 관리 코어 라우터 (Story 7.2~7.4).

- 코어 모듈 — 병원 도메인 지식 금지 (AD-14). 역할명 분기 없음 (AD-10).
- 인가는 전부 Depends(require_permission(P.ROLES_*)) 선언 (AD-6).
- is_system 역할: 수정·삭제·권한 회수 불가 (assert_role_mutable).
- role_fields는 삭제 없음 — is_active=false로만 숨김 (저장값 보존, AD-13).
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.authz import assert_role_mutable, invalidate_all_permissions, require_permission
from core.database import get_supabase_admin
from core.field_values import get_field_definitions
from core.permissions import P
from models.roles import (
    RoleCreate,
    RoleFieldCreate,
    RoleFieldUpdate,
    RolePermissionsUpdate,
    RoleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["roles"])

_ROLE_COLUMNS = "id, name, description, is_system, is_active, created_at, updated_at"
_PERMISSION_COLUMNS = "id, code, name, category, description"


def _get_role_or_404(role_id: UUID) -> dict:
    rows = (
        get_supabase_admin()
        .table("roles")
        .select(_ROLE_COLUMNS)
        .eq("id", str(role_id))
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "역할을 찾을 수 없습니다")
    return rows[0]


def _assert_role_name_available(name: str, exclude_id: str | None = None) -> None:
    query = get_supabase_admin().table("roles").select("id").eq("name", name)
    if exclude_id:
        query = query.neq("id", exclude_id)
    if (query.limit(1).execute()).data:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 역할 이름입니다")


# ------------------------------------------------------------
# 역할 CRUD (7.2)
# ------------------------------------------------------------


@router.get("/roles")
def list_roles(
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_READ))],
) -> list[dict]:
    client = get_supabase_admin()
    roles = (
        client.table("roles").select(_ROLE_COLUMNS).order("created_at").execute()
    ).data or []
    assignment_rows = (client.table("user_roles").select("role_id").execute()).data or []
    counts = Counter(row["role_id"] for row in assignment_rows)
    return [{**role, "user_count": counts.get(role["id"], 0)} for role in roles]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> dict:
    _assert_role_name_available(body.name)
    rows = (
        get_supabase_admin()
        .table("roles")
        .insert({"name": body.name, "description": body.description})
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "역할 생성에 실패했습니다")
    return {**rows[0], "user_count": 0}


@router.get("/roles/{role_id}")
def get_role(
    role_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_READ))],
) -> dict:
    role = _get_role_or_404(role_id)
    perm_rows = (
        get_supabase_admin()
        .table("role_permissions")
        .select(f"permissions({_PERMISSION_COLUMNS})")
        .eq("role_id", str(role_id))
        .execute()
    ).data or []
    permissions = sorted(
        (row["permissions"] for row in perm_rows if row.get("permissions")),
        key=lambda p: p["code"],
    )
    fields = get_field_definitions(str(role_id), active_only=False)
    return {**role, "permissions": permissions, "fields": fields}


@router.patch("/roles/{role_id}")
def update_role(
    role_id: UUID,
    body: RoleUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> dict:
    role = _get_role_or_404(role_id)
    assert_role_mutable(role)  # 시스템 역할은 수정 불가 (403)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "수정할 항목이 없습니다")
    if "name" in update_data and update_data["name"] != role["name"]:
        _assert_role_name_available(update_data["name"], exclude_id=str(role_id))
    rows = (
        get_supabase_admin()
        .table("roles")
        .update(update_data)
        .eq("id", str(role_id))
        .execute()
    ).data or []
    return rows[0] if rows else _get_role_or_404(role_id)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> None:
    role = _get_role_or_404(role_id)
    assert_role_mutable(role)  # 시스템 역할 삭제 불가 (403)
    client = get_supabase_admin()
    # FK RESTRICT(user_roles.role_id)를 사전 검사로 친절한 409로 변환
    holders = (
        client.table("user_roles")
        .select("user_id")
        .eq("role_id", str(role_id))
        .limit(1)
        .execute()
    ).data or []
    if holders:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "이 역할을 보유한 사용자가 있어 삭제할 수 없습니다"
        )
    client.table("roles").delete().eq("id", str(role_id)).execute()


# ------------------------------------------------------------
# 권한 카탈로그 · 역할-권한 조합 (7.3)
# ------------------------------------------------------------


@router.get("/permissions")
def list_permissions(
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_READ))],
) -> list[dict]:
    # 평탄 배열 — category 그룹핑은 프론트 몫
    return (
        get_supabase_admin()
        .table("permissions")
        .select(_PERMISSION_COLUMNS)
        .order("code")
        .execute()
    ).data or []


@router.put("/roles/{role_id}/permissions")
def replace_role_permissions(
    role_id: UUID,
    body: RolePermissionsUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> dict:
    role = _get_role_or_404(role_id)
    client = get_supabase_admin()

    requested = {str(pid) for pid in body.permission_ids}
    if requested:
        known_rows = (
            client.table("permissions").select("id").in_("id", sorted(requested)).execute()
        ).data or []
        unknown = requested - {row["id"] for row in known_rows}
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "존재하지 않는 권한이 포함되어 있습니다")

    current_rows = (
        client.table("role_permissions")
        .select("permission_id")
        .eq("role_id", str(role_id))
        .execute()
    ).data or []
    current = {row["permission_id"] for row in current_rows}

    to_remove = current - requested
    to_add = requested - current
    if to_remove:
        # 시스템 역할은 권한 회수 불가 — 추가만 허용 (7.3 AC)
        assert_role_mutable(role)
        client.table("role_permissions").delete().eq("role_id", str(role_id)).in_(
            "permission_id", sorted(to_remove)
        ).execute()
    if to_add:
        client.table("role_permissions").insert(
            [{"role_id": str(role_id), "permission_id": pid} for pid in sorted(to_add)]
        ).execute()

    if to_remove or to_add:
        # 이 역할 보유 전 사용자에게 즉시 반영 — 전체 캐시 무효화 (AD-11)
        invalidate_all_permissions()
        logger.info(
            "역할 권한 변경 role=%s by=%s +%d -%d",
            role_id, current_user.get("sub"), len(to_add), len(to_remove),
        )
    return {"role_id": str(role_id), "permission_ids": sorted(requested)}


# ------------------------------------------------------------
# 역할별 입력필드 정의 — 노코드 폼 빌더 (7.4)
# ------------------------------------------------------------


@router.get("/roles/{role_id}/fields")
def list_role_fields(
    role_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_READ))],
    active: Annotated[bool | None, Query(description="true면 활성 필드만")] = None,
) -> list[dict]:
    _get_role_or_404(role_id)
    return get_field_definitions(str(role_id), active_only=active is True)


@router.post("/roles/{role_id}/fields", status_code=status.HTTP_201_CREATED)
def create_role_field(
    role_id: UUID,
    body: RoleFieldCreate,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> dict:
    _get_role_or_404(role_id)
    client = get_supabase_admin()
    duplicate = (
        client.table("role_fields")
        .select("id")
        .eq("role_id", str(role_id))
        .eq("field_key", body.field_key)
        .limit(1)
        .execute()
    ).data or []
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 field_key입니다")
    rows = (
        client.table("role_fields")
        .insert({"role_id": str(role_id), **body.model_dump()})
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "필드 생성에 실패했습니다")
    return rows[0]


@router.patch("/roles/{role_id}/fields/{field_id}")
def update_role_field(
    role_id: UUID,
    field_id: UUID,
    body: RoleFieldUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.ROLES_MANAGE))],
) -> dict:
    # field_key·field_type은 모델(extra=forbid)에서 차단 — 저장값 정합성 보호
    client = get_supabase_admin()
    existing = (
        client.table("role_fields")
        .select("id")
        .eq("id", str(field_id))
        .eq("role_id", str(role_id))
        .limit(1)
        .execute()
    ).data or []
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "필드를 찾을 수 없습니다")
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "수정할 항목이 없습니다")
    rows = (
        client.table("role_fields")
        .update(update_data)
        .eq("id", str(field_id))
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "필드 수정에 실패했습니다")
    return rows[0]
