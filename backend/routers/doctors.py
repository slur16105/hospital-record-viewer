from __future__ import annotations
import secrets
import string
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError as PostgrestAPIError

from core.auth import require_admin
from core.database import get_supabase_admin, get_supabase_for_user
from models.doctors import DoctorCreate, DoctorCreatedOut, DoctorOut, DoctorUpdate

router = APIRouter(prefix="/doctors", tags=["doctors"])

_DOCTOR_SELECT = (
    "id, user_id, license_number, is_active, is_active, departments(name, id), "
    "user_profiles!inner(name, is_active)"
)

_LIST_SELECT = (
    "id, user_id, license_number, is_active, department_id, departments(name)"
)


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isdigit() for c in pw)
            and any(c.isalpha() for c in pw)
        ):
            return pw


def _flatten_doctor(row: dict, email: str = "") -> dict:
    profile = row.get("user_profiles") or {}
    dept = row.get("departments") or {}
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": profile.get("name", ""),
        "email": email,
        "department_id": row.get("department_id") or (dept.get("id", "")),
        "department_name": dept.get("name", ""),
        "license_number": row["license_number"],
        "is_active": row.get("is_active", True),
    }


@router.get("", response_model=list[DoctorOut])
async def list_doctors(
    current_user: Annotated[dict, Depends(require_admin)],
) -> list[DoctorOut]:
    admin = get_supabase_admin()
    result = (
        admin.table("doctors")
        .select("id, user_id, license_number, is_active, department_id, departments(name, id), user_profiles(name)")
        .order("user_profiles(name)")
        .execute()
    )
    rows = result.data or []

    # Batch-fetch emails from auth
    user_ids = [r["user_id"] for r in rows]
    email_map: dict = {}
    if user_ids:
        users_resp = admin.auth.admin.list_users()
        for u in (users_resp or []):
            if u.id in user_ids:
                email_map[u.id] = u.email or ""

    return [
        DoctorOut(
            id=r["id"],
            user_id=r["user_id"],
            name=(r.get("user_profiles") or {}).get("name", ""),
            email=email_map.get(r["user_id"], ""),
            department_id=r["department_id"],
            department_name=(r.get("departments") or {}).get("name", ""),
            license_number=r["license_number"],
            is_active=r.get("is_active", True),
        )
        for r in rows
    ]


@router.post("", response_model=DoctorCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    body: DoctorCreate,
    current_user: Annotated[dict, Depends(require_admin)],
) -> DoctorCreatedOut:
    admin = get_supabase_admin()
    temp_password = _generate_temp_password()

    # 1. Create auth user
    try:
        auth_resp = admin.auth.admin.create_user({
            "email": body.email,
            "password": temp_password,
            "email_confirm": True,
        })
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "duplicate" in msg or "exists" in msg:
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
        raise HTTPException(status_code=500, detail="계정 생성 중 오류가 발생했습니다")

    new_user_id = auth_resp.user.id

    try:
        # 2. user_profiles
        admin.table("user_profiles").insert({
            "user_id": new_user_id,
            "name": body.name,
            "role": "doctor",
            "must_change_password": True,
        }).execute()

        # 3. doctors row
        doctor_result = (
            admin.table("doctors")
            .insert({
                "user_id": new_user_id,
                "department_id": str(body.department_id),
                "license_number": body.license_number,
            })
            .select("id, user_id, license_number, is_active, department_id, departments(name, id)")
            .execute()
        )
    except Exception:
        # rollback: delete auth user
        try:
            admin.auth.admin.delete_user(new_user_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="계정 생성 중 오류가 발생했습니다")

    if not doctor_result.data:
        try:
            admin.auth.admin.delete_user(new_user_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="계정 생성 중 오류가 발생했습니다")

    row = doctor_result.data[0]
    dept = row.get("departments") or {}
    return DoctorCreatedOut(
        id=row["id"],
        user_id=new_user_id,
        name=body.name,
        email=body.email,
        department_id=row["department_id"],
        department_name=dept.get("name", ""),
        license_number=row["license_number"],
        is_active=row.get("is_active", True),
        temp_password=temp_password,
    )


@router.patch("/{doctor_id}", response_model=DoctorOut)
async def update_doctor(
    doctor_id: UUID,
    body: DoctorUpdate,
    current_user: Annotated[dict, Depends(require_admin)],
) -> DoctorOut:
    admin = get_supabase_admin()
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")

    # Split fields between tables
    profile_update: dict = {}
    doctor_update: dict = {}

    if "name" in update_data:
        profile_update["name"] = update_data["name"]
    if "department_id" in update_data:
        doctor_update["department_id"] = str(update_data["department_id"])
    if "license_number" in update_data:
        doctor_update["license_number"] = update_data["license_number"]
    if "is_active" in update_data:
        doctor_update["is_active"] = update_data["is_active"]
        profile_update["is_active"] = update_data["is_active"]

    # Fetch doctor to get user_id
    existing = admin.table("doctors").select("user_id, department_id, license_number, is_active").eq("id", str(doctor_id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = existing.data[0]["user_id"]

    if profile_update:
        admin.table("user_profiles").update(profile_update).eq("user_id", user_id).execute()

    if doctor_update:
        try:
            admin.table("doctors").update(doctor_update).eq("id", str(doctor_id)).execute()
        except PostgrestAPIError as e:
            raise HTTPException(status_code=500, detail="수정 중 오류가 발생했습니다")

    # Re-fetch for response
    result = (
        admin.table("doctors")
        .select("id, user_id, license_number, is_active, department_id, departments(name, id), user_profiles(name)")
        .eq("id", str(doctor_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Not found")
    row = result.data[0]
    dept = row.get("departments") or {}
    profile = row.get("user_profiles") or {}
    user_resp = admin.auth.admin.get_user_by_id(user_id)
    email = user_resp.user.email if user_resp and user_resp.user else ""
    return DoctorOut(
        id=row["id"],
        user_id=row["user_id"],
        name=profile.get("name", ""),
        email=email,
        department_id=row["department_id"],
        department_name=dept.get("name", ""),
        license_number=row["license_number"],
        is_active=row.get("is_active", True),
    )


@router.post("/{doctor_id}/reset-password", response_model=dict)
async def reset_doctor_password(
    doctor_id: UUID,
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    admin = get_supabase_admin()
    existing = admin.table("doctors").select("user_id").eq("id", str(doctor_id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = existing.data[0]["user_id"]

    temp_password = _generate_temp_password()
    admin.auth.admin.update_user_by_id(user_id, {"password": temp_password})
    admin.table("user_profiles").update({"must_change_password": True}).eq("user_id", user_id).execute()

    return {"temp_password": temp_password}
