from __future__ import annotations
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_current_user
from core.database import get_supabase_admin
from models.doctor_patients import DoctorProfile, MyPatientItem, PatientSearchItem

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _get_doctor_row(user_id: str) -> dict:
    admin = get_supabase_admin()
    result = (
        admin.table("doctors")
        .select("id, department_id, license_number, departments!inner(name)")
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(403, "의사 계정이 아닙니다")
    return result.data[0]


@router.get("/profile", response_model=DoctorProfile)
def get_doctor_profile(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DoctorProfile:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    doctor = _get_doctor_row(user_id)
    profile = admin.table("user_profiles").select("name").eq("user_id", user_id).execute()
    name = profile.data[0]["name"] if profile.data else ""

    return DoctorProfile(
        doctor_id=doctor["id"],
        user_id=user_id,
        name=name,
        department_id=doctor["department_id"],
        department_name=doctor["departments"]["name"],
        license_number=doctor["license_number"],
    )


@router.get("/my-patients", response_model=list[MyPatientItem])
def get_my_patients(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[MyPatientItem]:
    user_id: str = current_user["sub"]
    admin = get_supabase_admin()

    doctor = _get_doctor_row(user_id)
    doctor_id = doctor["id"]

    records_result = (
        admin.table("medical_records")
        .select("patient_id, visited_at")
        .eq("doctor_id", doctor_id)
        .order("visited_at", desc=True)
        .execute()
    )
    rows = records_result.data or []

    patient_latest: dict = {}
    for r in rows:
        pid = r["patient_id"]
        if pid not in patient_latest:
            patient_latest[pid] = r["visited_at"]

    if not patient_latest:
        return []

    patient_ids = list(patient_latest.keys())
    patients_result = (
        admin.table("patients")
        .select("id, user_id, birth_date")
        .in_("id", patient_ids)
        .execute()
    )
    patients = patients_result.data or []

    user_ids = [p["user_id"] for p in patients]
    profiles_result = (
        admin.table("user_profiles")
        .select("user_id, name")
        .in_("user_id", user_ids)
        .execute()
    )
    name_map = {p["user_id"]: p["name"] for p in (profiles_result.data or [])}

    items = [
        MyPatientItem(
            id=p["id"],
            user_id=p["user_id"],
            name=name_map.get(p["user_id"], ""),
            birth_date=p["birth_date"],
            latest_visited_at=patient_latest.get(p["id"]),
        )
        for p in patients
    ]
    items.sort(key=lambda x: x.latest_visited_at or "", reverse=True)
    return items


@router.get("/patients/search", response_model=list[PatientSearchItem])
def search_patients(
    current_user: Annotated[dict, Depends(get_current_user)],
    name: Annotated[str | None, Query()] = None,
    birth_date: date | None = None,
) -> list[PatientSearchItem]:
    if not name and not birth_date:
        return []

    admin = get_supabase_admin()

    user_ids_filter: list[str] | None = None
    if name:
        profile_result = (
            admin.table("user_profiles")
            .select("user_id")
            .ilike("name", f"%{name}%")
            .eq("role", "patient")
            .execute()
        )
        user_ids_filter = [p["user_id"] for p in (profile_result.data or [])]
        if not user_ids_filter:
            return []

    query = admin.table("patients").select("id, user_id, birth_date, phone")
    if user_ids_filter is not None:
        query = query.in_("user_id", user_ids_filter)
    if birth_date:
        query = query.eq("birth_date", birth_date.isoformat())

    patients_result = query.limit(50).execute()
    patients = patients_result.data or []
    if not patients:
        return []

    user_ids = [p["user_id"] for p in patients]
    profiles_result = (
        admin.table("user_profiles")
        .select("user_id, name")
        .in_("user_id", user_ids)
        .execute()
    )
    name_map = {p["user_id"]: p["name"] for p in (profiles_result.data or [])}

    return [
        PatientSearchItem(
            id=p["id"],
            user_id=p["user_id"],
            name=name_map.get(p["user_id"], ""),
            birth_date=p["birth_date"],
            phone=p["phone"],
        )
        for p in patients
    ]
