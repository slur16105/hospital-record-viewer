"""진료기록 라우터 — 권한 코드 기반 인가 (Story 10.1, AD-6·AD-10).

접근 판정은 require_permission/require_any_permission + 신컬럼
(medical_records.patient_user_id / doctor_user_id)으로 일원화한다.
RLS·역할명 분기·doctors/patients 임베드에 의존하지 않는다.
식별자는 전부 user_id 기준이다 (00013 레거시 제거 대응):
  - doctor.id 응답 필드 = doctor_user_id
  - 생성 body.patient_id = 환자의 user_id
  - 목록 필터 쿼리파람 = patient_user_id
"""
from __future__ import annotations
import ipaddress
import logging
from datetime import date, timedelta
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from core.authz import require_any_permission, require_permission
from core.database import get_supabase_admin
from core.permissions import P
from models.medical_records import (
    MedicalRecordCreate,
    MedicalRecordDetail,
    MedicalRecordListItem,
    MedicalRecordPage,
    MedicalRecordUpdate,
    DoctorInfo,
)
from routers.hospital_fields import doctor_display_map, profile_name_map

logger = logging.getLogger(__name__)

router = APIRouter(tags=["medical-records"])

_ROOM_JOIN = "examination_rooms(room_number)"

_LIST_SELECT = (
    "id, visited_at, diagnosis, is_corrected, room_id, "
    f"doctor_user_id, patient_user_id, {_ROOM_JOIN}"
)

_DETAIL_SELECT = (
    "id, visited_at, diagnosis, chief_complaint, prescription, "
    "is_corrected, correction_note, corrected_at, created_at, room_id, "
    f"doctor_user_id, patient_user_id, {_ROOM_JOIN}"
)

_READ_ANY = require_any_permission(
    P.RECORDS_READ_ALL, P.RECORDS_READ_ASSIGNED, P.RECORDS_READ_OWN
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
    # action은 아직 enum('view_list','view_detail') — 확장은 10.2 범위.
    # resource_type/resource_id를 명시 기록한다 (00012 일반화 컬럼).
    payload: dict = {"user_id": user_id, "action": action, "resource_type": "medical_record"}
    if record_id:
        payload["resource_id"] = record_id
    if ip:
        payload["ip_address"] = ip
    try:
        get_supabase_admin().table("access_logs").insert(payload).execute()
    except Exception:  # 감사 로그 실패가 본 요청을 깨뜨리지 않도록, 단 조용히 삼키진 않는다
        logger.exception("access_logs 기록 실패 user_id=%s action=%s", user_id, action)


def _room_number_from_row(row: dict) -> str | None:
    rooms = row.get("examination_rooms")
    if isinstance(rooms, dict):
        return rooms.get("room_number")
    return None


def _doctor_info(row: dict, display_map: dict) -> DoctorInfo:
    display = display_map.get(row.get("doctor_user_id") or "", {})
    return DoctorInfo(
        id=row["doctor_user_id"],  # 의사의 user_id (00013: 레거시 doctors.id 대체)
        name=display.get("name", ""),
        department=display.get("department", ""),
    )


def _to_detail(row: dict, display_map: dict) -> MedicalRecordDetail:
    patient_user_id = row.get("patient_user_id")
    patient_name = (
        profile_name_map([patient_user_id]).get(patient_user_id) if patient_user_id else None
    )
    return MedicalRecordDetail(
        id=row["id"],
        patient_name=patient_name,
        visited_at=row["visited_at"],
        diagnosis=row["diagnosis"],
        is_corrected=row["is_corrected"],
        room_number=_room_number_from_row(row),
        doctor=_doctor_info(row, display_map),
        chief_complaint=row.get("chief_complaint"),
        prescription=row.get("prescription"),
        correction_note=row.get("correction_note"),
        corrected_at=row.get("corrected_at"),
        created_at=row["created_at"],
    )


def _apply_read_scope(query, permissions: frozenset, user_id: str):
    """권한 보유 조합 → 조회 스코프 필터 (AD-6: 백엔드가 유일한 판정자).

    read_all: 전체 / read_assigned: doctor_user_id == 본인 /
    read_own: patient_user_id == 본인. 복수 보유 시 OR 확장.
    """
    if P.RECORDS_READ_ALL in permissions:
        return query
    scopes = []
    if P.RECORDS_READ_ASSIGNED in permissions:
        scopes.append(f"doctor_user_id.eq.{user_id}")
    if P.RECORDS_READ_OWN in permissions:
        scopes.append(f"patient_user_id.eq.{user_id}")
    return query.or_(",".join(scopes))


def _can_read_record(row: dict, permissions: frozenset, user_id: str) -> bool:
    if P.RECORDS_READ_ALL in permissions:
        return True
    if P.RECORDS_READ_ASSIGNED in permissions and row.get("doctor_user_id") == user_id:
        return True
    if P.RECORDS_READ_OWN in permissions and row.get("patient_user_id") == user_id:
        return True
    return False


@router.get("/medical-records", response_model=MedicalRecordPage)
def list_medical_records(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(_READ_ANY)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    patient_user_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> MedicalRecordPage:
    user_id: str = current_user["sub"]
    permissions: frozenset = current_user["permissions"]
    admin = get_supabase_admin()

    query = admin.table("medical_records").select(_LIST_SELECT, count="exact")
    query = _apply_read_scope(query, permissions, user_id)

    if patient_user_id:
        query = query.eq("patient_user_id", str(patient_user_id))
    if from_date:
        query = query.gte("visited_at", from_date.isoformat())
    if to_date:
        query = query.lt("visited_at", (to_date + timedelta(days=1)).isoformat())

    offset = (page - 1) * page_size
    result = query.order("visited_at", desc=True).range(offset, offset + page_size - 1).execute()

    rows = result.data or []
    total = result.count or 0

    # patient_user_id 지정 조회에서 스코프 밖 기록이 존재하면 403 (첫 방문 빈 목록과 구분)
    if patient_user_id and not rows and total == 0 and P.RECORDS_READ_ALL not in permissions:
        any_records = (
            admin.table("medical_records")
            .select("id", count="exact")
            .eq("patient_user_id", str(patient_user_id))
            .limit(1)
            .execute()
        )
        if (any_records.count or 0) > 0:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "이 환자의 진료기록에 접근할 권한이 없습니다")

    display_map = doctor_display_map(
        sorted({r["doctor_user_id"] for r in rows if r.get("doctor_user_id")})
    )
    patient_names = profile_name_map(
        sorted({r["patient_user_id"] for r in rows if r.get("patient_user_id")})
    )
    items = [
        MedicalRecordListItem(
            id=r["id"],
            visited_at=r["visited_at"],
            diagnosis=r["diagnosis"],
            is_corrected=r["is_corrected"],
            room_number=_room_number_from_row(r),
            doctor=_doctor_info(r, display_map),
            patient_name=patient_names.get(r.get("patient_user_id") or ""),
        )
        for r in rows
    ]

    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_list", None, ip)

    return MedicalRecordPage(data=items, total=total, page=page, page_size=page_size)


@router.get("/medical-records/{record_id}", response_model=MedicalRecordDetail)
def get_medical_record(
    record_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(_READ_ANY)],
) -> MedicalRecordDetail:
    user_id: str = current_user["sub"]
    permissions: frozenset = current_user["permissions"]

    result = (
        get_supabase_admin()
        .table("medical_records")
        .select(_DETAIL_SELECT)
        .eq("id", str(record_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    raw = result.data[0]
    if not _can_read_record(raw, permissions, user_id):
        # 스코프 밖 기록은 존재 여부를 노출하지 않는다 (구 RLS 동작과 동일하게 404)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    display_map = doctor_display_map(
        [raw["doctor_user_id"]] if raw.get("doctor_user_id") else []
    )

    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_detail", str(record_id), ip)

    return _to_detail(raw, display_map)


@router.post("/medical-records", status_code=201, response_model=MedicalRecordDetail)
def create_medical_record(
    body: MedicalRecordCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(require_permission(P.RECORDS_CREATE))],
) -> MedicalRecordDetail:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    # body.patient_id = 환자의 user_id (00013: 레거시 patients.id 대체)
    patient = (
        admin.table("user_profiles")
        .select("user_id")
        .eq("user_id", str(body.patient_id))
        .execute()
    )
    if not patient.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "환자를 찾을 수 없습니다")

    payload: dict = {
        "patient_user_id": str(body.patient_id),
        "doctor_user_id": user_id,            # 작성자 본인 자동 설정
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
        admin.table("medical_records")
        .insert(payload)
        .select(_DETAIL_SELECT)
        .execute()
    )

    if not result.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "진료기록 저장에 실패했습니다")

    raw = result.data[0]
    display_map = doctor_display_map([user_id])

    ip = _client_ip(request)
    background_tasks.add_task(_log_access, user_id, "view_detail", raw["id"], ip)

    return _to_detail(raw, display_map)


@router.patch("/medical-records/{record_id}", response_model=MedicalRecordDetail)
def update_medical_record(
    record_id: UUID,
    body: MedicalRecordUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.RECORDS_UPDATE_OWN))],
) -> MedicalRecordDetail:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "변경할 내용이 없습니다")

    existing = (
        admin.table("medical_records")
        .select("id, doctor_user_id")
        .eq("id", str(record_id))
        .execute()
    )
    # 본인(doctor_user_id == sub) 작성 기록만 수정 가능 — 미존재와 동일 메시지(구 동작 유지)
    if not existing.data or existing.data[0].get("doctor_user_id") != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "수정 권한이 없거나 기록을 찾을 수 없습니다")

    result = (
        admin.table("medical_records")
        .update(update_data)
        .eq("id", str(record_id))
        .select(_DETAIL_SELECT)
        .execute()
    )

    if not result.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "수정에 실패했습니다")

    raw = result.data[0]
    display_map = doctor_display_map(
        [raw["doctor_user_id"]] if raw.get("doctor_user_id") else []
    )
    return _to_detail(raw, display_map)
