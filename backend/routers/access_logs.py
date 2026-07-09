from __future__ import annotations
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.authz import require_permission
from core.database import get_supabase_admin
from core.permissions import P
from models.access_logs import AccessLogOut, AccessLogPage

# Story 10.1: require_admin(역할명 판정) → logs:read 권한 선언 (AD-6·AD-10)
router = APIRouter(
    prefix="/access-logs",
    tags=["access-logs"],
    dependencies=[Depends(require_permission(P.LOGS_READ))],
)


@router.get("", response_model=AccessLogPage)
def list_access_logs(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    from_date: date | None = None,
    to_date: date | None = None,
    resource_type: Annotated[str | None, Query(max_length=50)] = None,
) -> AccessLogPage:
    admin = get_supabase_admin()

    # 00013 대응: 레거시 record_id 컬럼 대신 일반화 컬럼(resource_type/resource_id)만 읽는다.
    query = (
        admin.table("access_logs")
        .select("id, user_id, resource_type, resource_id, action, ip_address, created_at", count="exact")
        .order("created_at", desc=True)
    )
    if from_date:
        query = query.gte("created_at", from_date.isoformat())
    if to_date:
        query = query.lt("created_at", f"{to_date.isoformat()}T23:59:59")
    if resource_type:
        query = query.eq("resource_type", resource_type)

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).execute()
    rows = result.data or []
    total = result.count or 0

    # Batch-resolve user names and patient names
    user_ids = list({r["user_id"] for r in rows})
    # 진료기록 리소스만 환자 이름 해석 대상 (record_id 응답 필드는 이 resource_id로 채움)
    record_ids = list({
        r["resource_id"]
        for r in rows
        if r.get("resource_id") and r.get("resource_type") == "medical_record"
    })

    name_map: dict = {}
    if user_ids:
        profiles = admin.table("user_profiles").select("user_id, name").in_("user_id", user_ids).execute()
        name_map = {p["user_id"]: p["name"] for p in (profiles.data or [])}

    # 환자 이름은 신컬럼(patient_user_id) → user_profiles로 해석 (!inner 임베드 의존 제거)
    patient_map: dict = {}
    if record_ids:
        records = (
            admin.table("medical_records")
            .select("id, patient_user_id")
            .in_("id", record_ids)
            .execute()
        ).data or []
        patient_user_ids = list({r["patient_user_id"] for r in records if r.get("patient_user_id")})
        pname_map: dict = {}
        if patient_user_ids:
            rows2 = (
                admin.table("user_profiles")
                .select("user_id, name")
                .in_("user_id", patient_user_ids)
                .execute()
            ).data or []
            pname_map = {p["user_id"]: p["name"] for p in rows2}
        for rec in records:
            patient_map[rec["id"]] = pname_map.get(rec.get("patient_user_id"), "")

    items = [
        AccessLogOut(
            id=r["id"],
            user_id=r["user_id"],
            accessor_name=name_map.get(r["user_id"], ""),
            record_id=(
                r.get("resource_id") if r.get("resource_type") == "medical_record" else None
            ),
            patient_name=patient_map.get(
                r.get("resource_id") if r.get("resource_type") == "medical_record" else "", ""
            ),
            action=r["action"],
            ip_address=r.get("ip_address"),
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return AccessLogPage(data=items, total=total, page=page, page_size=page_size)
