from datetime import date, timedelta
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from core.auth import get_current_user
from core.database import get_supabase_for_user
from models.medical_records import MedicalRecordDetail, MedicalRecordListItem, MedicalRecordPage, DoctorInfo

router = APIRouter(tags=["medical-records"])

_LIST_SELECT = (
    "id, visited_at, diagnosis, is_corrected, "
    "doctors!inner(id, user_id, departments!inner(name))"
)

_DETAIL_SELECT = (
    "id, visited_at, diagnosis, chief_complaint, prescription, "
    "is_corrected, correction_note, corrected_at, created_at, "
    "doctors!inner(id, user_id, departments!inner(name))"
)


def _extract_token(request: Request) -> str:
    parts = request.headers.get("authorization", "").split(" ", 1)
    return parts[1] if len(parts) == 2 else ""


def _log_access(token: str, user_id: str, action: str, record_id: str | None, ip: str | None) -> None:
    client = get_supabase_for_user(token)
    payload: dict = {"user_id": user_id, "action": action}
    if record_id:
        payload["record_id"] = record_id
    if ip:
        payload["ip_address"] = ip
    client.table("access_logs").insert(payload).execute()


def _enrich_records(rows: list[dict], token: str) -> list[MedicalRecordListItem]:
    if not rows:
        return []

    user_ids = list({
        r["doctors"]["user_id"] for r in rows
        if r.get("doctors") and r["doctors"].get("user_id")
    })
    client = get_supabase_for_user(token)
    profiles = client.table("user_profiles").select("user_id, name").in_("user_id", user_ids).execute()
    name_map = {p["user_id"]: p["name"] for p in (profiles.data or [])}

    return [
        MedicalRecordListItem(
            id=r["id"],
            visited_at=r["visited_at"],
            diagnosis=r["diagnosis"],
            is_corrected=r["is_corrected"],
            doctor=DoctorInfo(
                id=r["doctors"]["id"],
                name=name_map.get(r["doctors"]["user_id"], ""),
                department=r["doctors"]["departments"]["name"],
            ),
        )
        for r in rows
    ]


@router.get("/medical-records", response_model=MedicalRecordPage)
async def list_medical_records(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    from_date: date | None = None,
    to_date: date | None = None,
) -> MedicalRecordPage:
    token = _extract_token(request)
    user_id: str = current_user["sub"]
    client = get_supabase_for_user(token)

    query = client.table("medical_records").select(_LIST_SELECT, count="exact")
    if from_date:
        query = query.gte("visited_at", from_date.isoformat())
    if to_date:
        query = query.lt("visited_at", (to_date + timedelta(days=1)).isoformat())

    offset = (page - 1) * page_size
    result = query.order("visited_at", desc=True).range(offset, offset + page_size - 1).execute()

    items = _enrich_records(result.data or [], token)
    ip = request.client.host if request.client else None
    background_tasks.add_task(_log_access, token, user_id, "view_list", None, ip)

    return MedicalRecordPage(data=items, total=result.count or 0, page=page, page_size=page_size)


@router.get("/medical-records/{record_id}", response_model=MedicalRecordDetail)
async def get_medical_record(
    record_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MedicalRecordDetail:
    token = _extract_token(request)
    user_id: str = current_user["sub"]
    client = get_supabase_for_user(token)

    result = (
        client.table("medical_records")
        .select(_DETAIL_SELECT)
        .eq("id", str(record_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    base = _enrich_records(result.data, token)[0]
    raw = result.data[0]

    ip = request.client.host if request.client else None
    background_tasks.add_task(_log_access, token, user_id, "view_detail", str(record_id), ip)

    return MedicalRecordDetail(
        id=base.id,
        visited_at=base.visited_at,
        diagnosis=base.diagnosis,
        doctor=base.doctor,
        is_corrected=base.is_corrected,
        chief_complaint=raw.get("chief_complaint"),
        prescription=raw.get("prescription"),
        correction_note=raw.get("correction_note"),
        corrected_at=raw.get("corrected_at"),
        created_at=raw["created_at"],
    )
