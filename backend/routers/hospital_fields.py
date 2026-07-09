"""병원 앱 모듈 공용 헬퍼 — 신 스키마(user_profiles + profile_field_values) 읽기 (Story 10.1).

AD-14: 병원 도메인 지식(면허번호·소속과·생년월일·연락처 필드)은 앱 모듈에만 둔다.
role_fields 시드 고정 UUID는 supabase/migrations/00011_rbac_seed.sql과 동기화.
"""
from __future__ import annotations

from typing import Any

from core.database import get_supabase_admin

# 00011 시드 role_fields 고정 UUID
FIELD_LICENSE_NUMBER = "c0000000-0000-0000-0000-000000000001"  # 의사: 면허번호 (value_text)
FIELD_DEPARTMENT_ID = "c0000000-0000-0000-0000-000000000002"   # 의사: 소속 진료과 (value_text=uuid)
FIELD_BIRTH_DATE = "c0000000-0000-0000-0000-000000000003"      # 환자: 생년월일 (value_date)
FIELD_PHONE = "c0000000-0000-0000-0000-000000000004"           # 환자: 연락처 (value_text)


def profile_name_map(user_ids: list[str]) -> dict[str, str]:
    """{user_id: user_profiles.name}"""
    if not user_ids:
        return {}
    rows = (
        get_supabase_admin()
        .table("user_profiles")
        .select("user_id, name")
        .in_("user_id", user_ids)
        .execute()
    ).data or []
    return {r["user_id"]: r["name"] for r in rows}


def field_value_map(role_field_id: str, user_ids: list[str], column: str) -> dict[str, Any]:
    """{user_id: profile_field_values.<column>} — 특정 필드 정의의 값 일괄 조회."""
    if not user_ids:
        return {}
    rows = (
        get_supabase_admin()
        .table("profile_field_values")
        .select(f"user_id, {column}")
        .eq("role_field_id", role_field_id)
        .in_("user_id", user_ids)
        .execute()
    ).data or []
    return {r["user_id"]: r[column] for r in rows if r.get(column) is not None}


def doctor_display_map(user_ids: list[str]) -> dict[str, dict[str, str]]:
    """{doctor_user_id: {"name", "department"}} — 의사 표시 정보를 신 스키마로 해석.

    이름은 user_profiles.name, 소속과는 field_values(department_id) → departments.name.
    (구 doctors ⋈ departments 임베드 대체 — CLAUDE.md 함정 #2의 !inner 의존 제거)
    """
    if not user_ids:
        return {}
    names = profile_name_map(user_ids)
    dept_ids = field_value_map(FIELD_DEPARTMENT_ID, user_ids, "value_text")

    dept_names: dict[str, str] = {}
    unique_depts = sorted(set(dept_ids.values()))
    if unique_depts:
        rows = (
            get_supabase_admin()
            .table("departments")
            .select("id, name")
            .in_("id", unique_depts)
            .execute()
        ).data or []
        dept_names = {r["id"]: r["name"] for r in rows}

    return {
        uid: {
            "name": names.get(uid, ""),
            "department": dept_names.get(dept_ids.get(uid, ""), ""),
        }
        for uid in user_ids
    }
