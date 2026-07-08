from __future__ import annotations
import ipaddress
import logging
from datetime import date, timedelta
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from core.auth import get_current_user
from core.database import get_supabase_admin, get_supabase_for_user
from models.medical_records import (
    MedicalRecordCreate,
    MedicalRecordDetail,
    MedicalRecordListItem,
    MedicalRecordPage,
    MedicalRecordUpdate,
    DoctorInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["medical-records"])

_DOCTOR_JOIN = "doctors!inner(id, user_id, departments!inner(name))"
_ROOM_JOIN = "examination_rooms(room_number)"

_LIST_SELECT = f"id, visited_at, diagnosis, is_corrected, room_id, {_DOCTOR_JOIN}, {_ROOM_JOIN}"

_DETAIL_SELECT = (
    "id, visited_at, diagnosis, chief_complaint, prescription, "
    f"is_corrected, correction_note, corrected_at, created_at, room_id, {_DOCTOR_JOIN}, {_ROOM_JOIN}"
)


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


def _client_ip(request: Request) -> str | None:
    # Railway 등 프록시 뒤에서는 request.client.host가 프록시 IP다.
    # X-Forwarded-For의 첫 번째(원 클라이언트) IP를 우선 사용하되, 형식을 검증한다.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        ip = _valid_ip(first)
        if ip:
            return ip
    peer = request.client.host if request.client else None
    return _valid_ip(peer)


def _log_access(user_id: str, action: str, record_id: str | None, ip: str | None) -> None:
    # 접근 로그는 service_role(admin) 클라이언트로 기록한다.
    # 유저 토큰 클라이언트는 RLS(access_logs_insert: user_id = auth.uid())에 막혀
    # 백그라운드 태스크에서 조용히 실패한다. 읽기(access_logs.py)도 admin을 쓰므로 일관됨.
    payload: dict = {"user_id": user_id, "action": action}
    if record_id:
        payload["record_id"] = record_id
    if ip:
        payload["ip_address"] = ip
    try:
        get_supabase_admin().table("access_logs").insert(payload).execute()
    except Exception:  # 감사 로그 실패가 본 요청을 깨뜨리지 않도록, 단 조용히 삼키진 않는다
        logger.exception("access_logs 기록 실패 user_id=%s action=%s", user_id, action)


def _resolve_doctor_name(client, user_id: str | None) -> str:
    if not user_id:
        return ""
    profiles = client.table("user_profiles").select("name").eq("user_id", user_id).execute()
    return profiles.data[0]["name"] if profiles.data else ""


def _room_number_from_row(row: dict) -> str | None:
    rooms = row.get("examination_rooms")
    if isinstance(rooms, dict):
        return rooms.get("room_number")
    return None


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
            room_number=_room_number_from_row(r),
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
def list_medical_records(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    patient_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> MedicalRecordPage:
    token: str = current_user["token"]
    user_id: str = current_user["sub"]
    client = get_supabase_for_user(token)

    query = client.table("medical_records").select(_LIST_SELECT, count="exact")

    if patient_id:
        query = query.eq("patient_id", str(patient_id))
    if from_date:
        query = query.gte("visited_at", from_date.isoformat())
    if to_date:
        query = query.lt("visited_at", (to_date + timedelta(days=1)).isoformat())

    offset = (page - 1) * page_size
    result = query.order("visited_at", desc=True).range(offset, offset + page_size - 1).execute()

    # If a patient_id was requested but no records returned, check if patient exists
    # to return 403 vs empty list for first-visit vs unauthorized access
    rows = result.data or []
    total = result.count or 0

    if patient_id and not rows and total == 0:
        admin = get_supabase_admin()
        patient = admin.table("patients").select("id").eq("id", str(patient_id)).execute()
        if patient.data:
            # Patient exists — check if they have ANY records
            any_records = (
                admin.table("medical_records")
                .select("id", count="exact")
                .eq("patient_id", str(patient_id))
                .limit(1)
                .execute()
            )
            if (any_records.count or 0) > 0:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "이 환자의 진료기록에 접근할 권한이 없습니다")

    items = _enrich_records(rows, client)
    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_list", None, ip)

    return MedicalRecordPage(data=items, total=total, page=page, page_size=page_size)


@router.get("/medical-records/{record_id}", response_model=MedicalRecordDetail)
def get_medical_record(
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

    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_detail", str(record_id), ip)

    return MedicalRecordDetail(
        id=raw["id"],
        visited_at=raw["visited_at"],
        diagnosis=raw["diagnosis"],
        is_corrected=raw["is_corrected"],
        room_number=_room_number_from_row(raw),
        doctor=DoctorInfo(
            id=raw["doctors"]["id"],
            name=doctor_name,
            department=raw["doctors"]["departments"]["name"],
        ),
        chief_complaint=raw.get("chief_complaint"),
        prescription=raw.get("prescription"),
        correction_note=raw.get("correction_note"),
        corrected_at=raw.get("corrected_at"),
        created_at=raw["created_at"],
    )


@router.post("/medical-records", status_code=201, response_model=MedicalRecordDetail)
def create_medical_record(
    body: MedicalRecordCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MedicalRecordDetail:
    token: str = current_user["token"]
    user_id: str = current_user["sub"]

    # Verify patient exists (admin — patient may not have prior records yet)
    admin = get_supabase_admin()
    patient = admin.table("patients").select("id").eq("id", str(body.patient_id)).execute()
    if not patient.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "환자를 찾을 수 없습니다")

    client = get_supabase_for_user(token)

    # Get current doctor's row (needs to be doctor to pass RLS)
    doctor_result = client.table("doctors").select("id").eq("user_id", user_id).execute()
    if not doctor_result.data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "의사 계정이 아닙니다")
    doctor_id = doctor_result.data[0]["id"]

    payload: dict = {
        "patient_id": str(body.patient_id),
        "doctor_id": doctor_id,
        "visited_at": body.visited_at.isoformat(),
        "diagnosis": body.diagnosis,
    }
    if body.chief_complaint is not None:
        payload["chief_complaint"] = body.chief_complaint
    if body.prescription is not None:
        payload["prescription"] = body.prescription
    if body.room_id is not None:
        payload["room_id"] = str(body.room_id)

    result = (
        client.table("medical_records")
        .insert(payload)
        .select(_DETAIL_SELECT)
        .execute()
    )

    if not result.data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "진료기록 저장 권한이 없습니다")

    raw = result.data[0]
    doctor_name = _resolve_doctor_name(client, raw["doctors"].get("user_id"))

    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_detail", raw["id"], ip)

    return MedicalRecordDetail(
        id=raw["id"],
        visited_at=raw["visited_at"],
        diagnosis=raw["diagnosis"],
        is_corrected=raw["is_corrected"],
        room_number=_room_number_from_row(raw),
        doctor=DoctorInfo(
            id=raw["doctors"]["id"],
            name=doctor_name,
            department=raw["doctors"]["departments"]["name"],
        ),
        chief_complaint=raw.get("chief_complaint"),
        prescription=raw.get("prescription"),
        correction_note=raw.get("correction_note"),
        corrected_at=raw.get("corrected_at"),
        created_at=raw["created_at"],
    )


@router.patch("/medical-records/{record_id}", response_model=MedicalRecordDetail)
def update_medical_record(
    record_id: UUID,
    body: MedicalRecordUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MedicalRecordDetail:
    token: str = current_user["token"]
    user_id: str = current_user["sub"]
    client = get_supabase_for_user(token)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "변경할 내용이 없습니다")

    result = (
        client.table("medical_records")
        .update(update_data)
        .eq("id", str(record_id))
        .select(_DETAIL_SELECT)
        .execute()
    )

    if not result.data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "수정 권한이 없거나 기록을 찾을 수 없습니다")

    raw = result.data[0]
    doctor_name = _resolve_doctor_name(client, raw["doctors"].get("user_id"))

    return MedicalRecordDetail(
        id=raw["id"],
        visited_at=raw["visited_at"],
        diagnosis=raw["diagnosis"],
        is_corrected=raw["is_corrected"],
        room_number=_room_number_from_row(raw),
        doctor=DoctorInfo(
            id=raw["doctors"]["id"],
            name=doctor_name,
            department=raw["doctors"]["departments"]["name"],
        ),
        chief_complaint=raw.get("chief_complaint"),
        prescription=raw.get("prescription"),
        correction_note=raw.get("correction_note"),
        corrected_at=raw.get("corrected_at"),
        created_at=raw["created_at"],
    )
