"""GET /me — 프론트 메뉴·가드의 단일 소스 (spine Conventions).

응답: { user, profile, roles: [...], primary_role, permissions: [...] }
- profile.field_values: {field_key: value} 평탄화 (프론트는 EAV를 모름 — AD-13)
- permissions: 보유 역할 권한의 합집합 (AD-11 캐시 경유)
- primary_role: is_primary 역할의 name (없으면 첫 역할, 역할 없으면 null)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.authz import get_user_permissions
from core.database import get_supabase_admin
from core.field_values import get_field_values_flat

router = APIRouter(tags=["me"])


@router.get("/me")
def get_me(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    user_id = current_user["sub"]
    client = get_supabase_admin()

    profile_rows = (
        client.table("user_profiles").select("*").eq("user_id", user_id).execute()
    ).data or []
    if not profile_rows:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
    profile = profile_rows[0]
    profile["field_values"] = get_field_values_flat(user_id)

    role_rows = (
        client.table("user_roles")
        .select("is_primary, roles(id, name, description, is_system, is_active)")
        .eq("user_id", user_id)
        .execute()
    ).data or []
    roles = []
    primary_role: str | None = None
    for row in role_rows:
        role = row.get("roles")
        if not role:
            continue
        roles.append({**role, "is_primary": row["is_primary"]})
        if row["is_primary"]:
            primary_role = role["name"]
    if primary_role is None and roles:
        primary_role = roles[0]["name"]

    return {
        "user": {"id": user_id, "email": current_user.get("email")},
        "profile": profile,
        "roles": roles,
        "primary_role": primary_role,
        "permissions": sorted(get_user_permissions(user_id)),
    }
