from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_admin
from core.database import get_supabase_admin
from models.patients_admin import PatientOut, PatientUpdate

router = APIRouter(prefix="/patients", tags=["patients-admin"])


def _build_patient_out(row: dict, email: str = "") -> PatientOut:
    profile = row.get("user_profiles") or {}
    return PatientOut(
        id=row["id"],
        user_id=row["user_id"],
        name=profile.get("name", ""),
        email=email,
        birth_date=row["birth_date"],
        phone=row["phone"],
        is_active=profile.get("is_active", True),
        created_at=str(row.get("created_at", "")),
    )


@router.get("", response_model=list[PatientOut])
async def list_patients(
    current_user: Annotated[dict, Depends(require_admin)],
) -> list[PatientOut]:
    admin = get_supabase_admin()
    result = (
        admin.table("patients")
        .select("id, user_id, birth_date, phone, created_at, user_profiles(name, is_active)")
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data or []

    user_ids = [r["user_id"] for r in rows]
    email_map: dict = {}
    if user_ids:
        users_resp = admin.auth.admin.list_users()
        for u in (users_resp or []):
            if u.id in user_ids:
                email_map[u.id] = u.email or ""

    return [_build_patient_out(r, email_map.get(r["user_id"], "")) for r in rows]


@router.patch("/{patient_id}", response_model=PatientOut)
async def update_patient(
    patient_id: UUID,
    body: PatientUpdate,
    current_user: Annotated[dict, Depends(require_admin)],
) -> PatientOut:
    admin = get_supabase_admin()
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")

    existing = admin.table("patients").select("user_id, birth_date, phone, created_at").eq("id", str(patient_id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = existing.data[0]["user_id"]

    patients_update: dict = {}
    profile_update: dict = {}

    if "birth_date" in update_data:
        patients_update["birth_date"] = str(update_data["birth_date"])
    if "phone" in update_data:
        patients_update["phone"] = update_data["phone"]
    if "name" in update_data:
        profile_update["name"] = update_data["name"]
    if "is_active" in update_data:
        profile_update["is_active"] = update_data["is_active"]

    if patients_update:
        admin.table("patients").update(patients_update).eq("id", str(patient_id)).execute()
    if profile_update:
        admin.table("user_profiles").update(profile_update).eq("user_id", user_id).execute()

    result = (
        admin.table("patients")
        .select("id, user_id, birth_date, phone, created_at, user_profiles(name, is_active)")
        .eq("id", str(patient_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Not found")

    user_resp = admin.auth.admin.get_user_by_id(user_id)
    email = user_resp.user.email if user_resp and user_resp.user else ""
    return _build_patient_out(result.data[0], email)
