from __future__ import annotations
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.auth import get_current_user
from core.database import get_supabase_admin
from models.access_logs import AccessLogOut, AccessLogPage

router = APIRouter(prefix="/access-logs", tags=["access-logs"])


@router.get("", response_model=AccessLogPage)
async def list_access_logs(
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    from_date: date | None = None,
    to_date: date | None = None,
) -> AccessLogPage:
    admin = get_supabase_admin()

    query = (
        admin.table("access_logs")
        .select("id, user_id, record_id, action, ip_address, created_at", count="exact")
        .order("created_at", desc=True)
    )
    if from_date:
        query = query.gte("created_at", from_date.isoformat())
    if to_date:
        query = query.lt("created_at", f"{to_date.isoformat()}T23:59:59")

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).execute()
    rows = result.data or []
    total = result.count or 0

    # Batch-resolve user names and patient names
    user_ids = list({r["user_id"] for r in rows})
    record_ids = list({r["record_id"] for r in rows if r.get("record_id")})

    name_map: dict = {}
    if user_ids:
        profiles = admin.table("user_profiles").select("user_id, name").in_("user_id", user_ids).execute()
        name_map = {p["user_id"]: p["name"] for p in (profiles.data or [])}

    patient_map: dict = {}
    if record_ids:
        records = (
            admin.table("medical_records")
            .select("id, patients!inner(user_id, user_profiles!inner(name))")
            .in_("id", record_ids)
            .execute()
        )
        for rec in (records.data or []):
            try:
                pname = rec["patients"]["user_profiles"]["name"]
            except (KeyError, TypeError):
                pname = ""
            patient_map[rec["id"]] = pname

    items = [
        AccessLogOut(
            id=r["id"],
            user_id=r["user_id"],
            accessor_name=name_map.get(r["user_id"], ""),
            record_id=r.get("record_id"),
            patient_name=patient_map.get(r.get("record_id", ""), ""),
            action=r["action"],
            ip_address=r.get("ip_address"),
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return AccessLogPage(data=items, total=total, page=page, page_size=page_size)
