from datetime import date, timedelta
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from core.auth import get_current_user
from core.database import get_supabase_for_user
from models.medical_records import MedicalRecordDetail, MedicalRecordListItem, MedicalRecordPage, DoctorInfo

router = APIRouter(tags=["medical-records"])

_DOCTOR_JOIN = "doctors!inner(id, user_id, departments!inner(name))"

_LIST_SELECT = f"id, visited_at, diagnosis, is_corrected, {_DOCTOR_JOIN}"

_DETAIL_SELECT = (
    "id, visited_at, diagnosis, chief_complaint, prescription, "
    f"is_corrected, correction_note, corrected_at, created_at, {_DOCTOR_JOIN}"
)


def _log_access(client, user_id: str, action: str, record_id: str | None, ip: str | None) -> None:
    payload: dict = {"user_id": user_id, "action": action}
    if record_id:
        payload["record_id"] = record_id
    if ip:
        payload["ip_address"] = ip
    client.table("access_logs").insert(payload).execute()


def _resolve_doctor_name(client, user_id: str | None) -> str:
    if not user_id:
        return ""
    profiles = client.table("user_profiles").select("name").eq("user_id", user_id).execute()
    return profiles.data[0]["name"] if profiles.data else ""


def _enrich_records(rows: list[dict], client) -> list[MedicalRecordListItem]:
    if not rows:
        return []

    user_ids = list({
        r["doctors"]["user_id"] for r in rows
        if r.get("doctors") and r["doctors"].get("user_id")
    })

    if not user_ids:
        name_map: dict = {}
    else:
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
                name=name_map.get(r["doctors"].get("user_id", ""), ""),
                department=r["doctors"]["departments"]["name"],
            ),
        )
        for r in rows
        if r.get("doctors") and r["doctors"].get("departments")
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
    token: str = current_user["token"]
    user_id: str = current_user["sub"]
    client = get_supabase_for_user(token)

    query = client.table("medical_records").select(_LIST_SELECT, count="exact")
    if from_date:
        query = query.gte("visited_at", from_date.isoformat())
    if to_date:
        query = query.lt("visited_at", (to_date + timedelta(days=1)).isoformat())

    offset = (page - 1) * page_size
    result = query.order("visited_at", desc=True).range(offset, offset + page_size - 1).execute()

    items = _enrich_records(result.data or [], client)
    ip = request.client.host if request.client else None
    background_tasks.add_task(_log_access, client, user_id, "view_list", None, ip)

    return MedicalRecordPage(data=items, total=result.count or 0, page=page, page_size=page_size)


@router.get("/medical-records/{record_id}", response_model=MedicalRecordDetail)
async def get_medical_record(
    record_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MedicalRecordDetail:
    token: str = current_user["token"]
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

    raw = result.data[0]
    if not raw.get("doctors") or not raw["doctors"].get("departments"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    doctor_user_id = raw["doctors"].get("user_id")
    doctor_name = _resolve_doctor_name(client, doctor_user_id)

    ip = request.client.host if request.client else None
    background_tasks.add_task(_log_access, client, user_id, "view_detail", str(record_id), ip)

    return MedicalRecordDetail(
        id=raw["id"],
        visited_at=raw["visited_at"],
        diagnosis=raw["diagnosis"],
        doctor=DoctorInfo(
            id=raw["doctors"]["id"],
            name=doctor_name,
            department=raw["doctors"]["departments"]["name"],
        ),
        is_corrected=raw["is_corrected"],
        chief_complaint=raw.get("chief_complaint"),
        prescription=raw.get("prescription"),
        correction_note=raw.get("correction_note"),
        corrected_at=raw.get("corrected_at"),
        created_at=raw["created_at"],
    )
