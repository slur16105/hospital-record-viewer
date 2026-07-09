"""의사 포털 라우터 — 권한 코드 기반 인가 (Story 10.1, AD-6·AD-10).

담당 판정은 medical_records.doctor_user_id == 본인(sub), 프로필·환자 정보는
신 스키마(user_profiles + profile_field_values)에서 읽는다.
식별자는 전부 user_id 기준이다 (00013 레거시 제거 대응): 응답 id = user_id.
"""
from __future__ import annotations
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from core.authz import require_permission
from core.database import get_supabase_admin
from core.field_values import get_field_values_flat, search_users_by_field
from core.permissions import P
from models.doctor_patients import DoctorProfile, MyPatientItem, PatientSearchItem
from routers.hospital_fields import (
    FIELD_BIRTH_DATE,
    FIELD_PHONE,
    field_value_map,
    profile_name_map,
)

router = APIRouter(prefix="/doctor", tags=["doctor"])

_SEARCH_LIMIT = 50


@router.get("/profile", response_model=DoctorProfile)
def get_doctor_profile(
    current_user: Annotated[dict, Depends(require_permission(P.RECORDS_READ_ASSIGNED))],
) -> DoctorProfile:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    # 신 스키마: 이름=user_profiles, 면허번호·소속과=profile_field_values (AD-13 평탄화)
    profile = admin.table("user_profiles").select("name").eq("user_id", user_id).execute()
    name = profile.data[0]["name"] if profile.data else ""
    values = get_field_values_flat(user_id)
    department_id = values.get("department_id")
    license_number = values.get("license_number") or ""

    # 의사 여부 판정: 소속과 필드값 보유 (레거시 doctors 테이블 역조회 제거)
    if not department_id:
        raise HTTPException(403, "의사 계정이 아닙니다")

    dept = admin.table("departments").select("name").eq("id", department_id).execute()
    department_name = dept.data[0]["name"] if dept.data else ""

    return DoctorProfile(
        doctor_id=user_id,  # user_id (00013: 레거시 doctors.id 대체)
        user_id=user_id,
        name=name,
        department_id=department_id,
        department_name=department_name,
        license_number=license_number,
    )


@router.get("/my-patients", response_model=list[MyPatientItem])
def get_my_patients(
    current_user: Annotated[dict, Depends(require_permission(P.RECORDS_READ_ASSIGNED))],
) -> list[MyPatientItem]:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    # 담당 환자 = medical_records.doctor_user_id == 본인 (신컬럼 판정)
    records_result = (
        admin.table("medical_records")
        .select("patient_user_id, visited_at")
        .eq("doctor_user_id", user_id)
        .order("visited_at", desc=True)
        .execute()
    )
    rows = records_result.data or []

    latest_by_user: dict = {}
    for r in rows:
        puid = r.get("patient_user_id")
        if not puid or puid in latest_by_user:
            continue
        latest_by_user[puid] = r["visited_at"]

    if not latest_by_user:
        return []

    patient_user_ids = list(latest_by_user.keys())
    name_map = profile_name_map(patient_user_ids)
    birth_map = field_value_map(FIELD_BIRTH_DATE, patient_user_ids, "value_date")

    items = [
        MyPatientItem(
            id=uid,  # user_id (00013: 레거시 patients.id 대체)
            user_id=uid,
            name=name_map.get(uid, ""),
            birth_date=birth_map[uid],
            latest_visited_at=latest_by_user.get(uid),
        )
        for uid in patient_user_ids
        if uid in birth_map  # 생년월일 필드값 없는 사용자는 응답 스키마상 표현 불가 — 제외
    ]
    items.sort(key=lambda x: x.latest_visited_at or "", reverse=True)
    return items


@router.get("/patients/search", response_model=list[PatientSearchItem])
def search_patients(
    current_user: Annotated[dict, Depends(require_permission(P.PATIENTS_SEARCH))],
    name: Annotated[str | None, Query()] = None,
    birth_date: date | None = None,
) -> list[PatientSearchItem]:
    if not name and not birth_date:
        return []

    admin = get_supabase_admin()

    # '환자 역할 보유자' 판정이 아니라 검색 가능 필드 + 이름 기반 (AD-10·AD-13)
    matched: set | None = None
    if name:
        profile_result = (
            admin.table("user_profiles")
            .select("user_id")
            .ilike("name", f"%{name}%")
            .limit(_SEARCH_LIMIT)
            .execute()
        )
        matched = {p["user_id"] for p in (profile_result.data or [])}
        if not matched:
            return []
    if birth_date:
        # is_searchable 필드 기반 검색 (core.field_values) — 생년월일 완전일치
        birth_matches = set(
            search_users_by_field(
                "birth_date", birth_date.isoformat(), exact=True, limit=_SEARCH_LIMIT
            )
        )
        matched = matched & birth_matches if matched is not None else birth_matches

    user_ids = sorted(matched or set())[:_SEARCH_LIMIT]
    if not user_ids:
        return []

    # 응답 id = user_id — 기록 작성 API(body.patient_id)도 user_id를 받는다
    name_map = profile_name_map(user_ids)
    birth_map = field_value_map(FIELD_BIRTH_DATE, user_ids, "value_date")
    phone_map = field_value_map(FIELD_PHONE, user_ids, "value_text")

    return [
        PatientSearchItem(
            id=uid,
            user_id=uid,
            name=name_map.get(uid, ""),
            birth_date=birth_map[uid],
            phone=phone_map.get(uid, ""),
        )
        for uid in user_ids
        if uid in birth_map  # 필수 필드값(생년월일) 없는 사용자 제외
    ]
