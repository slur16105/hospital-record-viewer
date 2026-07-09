"""통합 사용자 관리 코어 라우터 (Story 8.1~8.3, FR-20~22).

- 코어 모듈 — 병원 도메인 지식 금지 (AD-14). 역할명 분기 없음 (AD-10).
- 인가는 전부 Depends(require_permission(P.USERS_* / PASSWORD_RESET_OTHERS)) 선언.
- 필드값 쓰기는 전부 core.field_values(validate_and_save_field_values) 경유 (AD-13).
- 역할 변경은 invalidate_user_permissions + access_logs(role_change) 기록 (AD-11).
"""
from __future__ import annotations

import ipaddress
import logging
import secrets
import string
from typing import Any, Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from core.authz import assert_not_last_admin, invalidate_user_permissions, require_permission
from core.database import get_supabase_admin
from core.field_values import (
    get_field_definitions,
    get_field_values_flat,
    search_users_by_field,
    validate_and_save_field_values,
)
from core.permissions import P, ROLE_ADMIN_ID
from models.users import UserCreate, UserRolesUpdate, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_PROFILE_COLUMNS = "user_id, name, avatar_url, is_active, must_change_password, updated_at"
_ROLE_JOIN = "role_id, is_primary, roles(id, name, description, is_system, is_active)"


# ------------------------------------------------------------
# 공용 헬퍼
# ------------------------------------------------------------


def _generate_temp_password(length: int = 12) -> str:
    # 임시 비밀번호 규칙: 문자+숫자 최소 1개. AD-14 경계 유지를 위해 로컬 정의.
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = _valid_ip(forwarded.split(",", 1)[0].strip())
        if ip:
            return ip
    peer = request.client.host if request.client else None
    return _valid_ip(peer)


def _log_role_change(actor_id: str, target_user_id: str, ip: str | None) -> None:
    """access_logs에 역할 변경 감사 기록 (BackgroundTask — 본 요청을 깨뜨리지 않음)."""
    payload: dict[str, Any] = {
        "user_id": actor_id,
        "action": "role_change",
        "resource_type": "user",
        "resource_id": target_user_id,
    }
    if ip:
        payload["ip_address"] = ip
    try:
        get_supabase_admin().table("access_logs").insert(payload).execute()
    except Exception:
        logger.exception(
            "access_logs 기록 실패 actor=%s target=%s action=role_change",
            actor_id, target_user_id,
        )


def _email_map(user_ids: set) -> dict:
    """auth admin list_users 페이지네이션으로 {user_id: email} 구성."""
    wanted = {str(uid) for uid in user_ids}
    emails: dict[str, str] = {}
    if not wanted:
        return emails
    admin = get_supabase_admin()
    page, per_page = 1, 200
    while True:
        users = admin.auth.admin.list_users(page=page, per_page=per_page) or []
        for u in users:
            if u.id in wanted:
                emails[u.id] = u.email or ""
        if len(users) < per_page or len(emails) >= len(wanted):
            return emails
        page += 1


def _get_profile_or_404(user_id: UUID) -> dict:
    rows = (
        get_supabase_admin()
        .table("user_profiles")
        .select(_PROFILE_COLUMNS)
        .eq("user_id", str(user_id))
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다")
    return rows[0]


def _fetch_roles_validated(role_ids: list[UUID]) -> list[dict]:
    """role_ids가 전부 존재하고 활성인지 검증 후 roles 행 반환 (아니면 400)."""
    ids = [str(rid) for rid in role_ids]
    rows = (
        get_supabase_admin()
        .table("roles")
        .select("id, name, is_system, is_active")
        .in_("id", ids)
        .execute()
    ).data or []
    found = {row["id"] for row in rows}
    missing = set(ids) - found
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "존재하지 않는 역할이 포함되어 있습니다")
    inactive = [row["name"] for row in rows if not row.get("is_active", True)]
    if inactive:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"비활성 역할은 부여할 수 없습니다: {', '.join(sorted(inactive))}",
        )
    return rows


def _user_role_rows(user_id: str) -> list[dict]:
    return (
        get_supabase_admin()
        .table("user_roles")
        .select(_ROLE_JOIN)
        .eq("user_id", user_id)
        .execute()
    ).data or []


def _roles_summary(role_rows: list[dict]) -> tuple[list[dict], str | None]:
    roles = []
    primary_role_id = None
    for row in role_rows:
        role = row.get("roles")
        if not role:
            continue
        roles.append({**role, "is_primary": row["is_primary"]})
        if row["is_primary"]:
            primary_role_id = role["id"]
    return roles, primary_role_id


def _save_field_values_by_role(
    user_id: str, role_ids: list[str], values: dict, merge_existing: bool = False
) -> dict:
    """제공된 field_values를 역할별 필드 정의로 나눠 검증·저장 (AD-13).

    - 각 역할의 활성 필드 정의에 속한 키만 해당 역할로 라우팅
    - 어느 역할에도 없는 키는 400 {field_key: "알 수 없는 필드입니다"}
    - merge_existing=True(부분 수정): 기존 저장값과 병합해 required 검사를 통과시킨다
    """
    existing = get_field_values_flat(user_id) if merge_existing else {}
    routed: set = set()
    saved: dict = {}
    for role_id in role_ids:
        definitions = get_field_definitions(role_id, active_only=True)
        if not definitions:
            continue
        keys = {d["field_key"] for d in definitions}
        subset = {k: v for k, v in values.items() if k in keys}
        routed |= set(subset)
        if merge_existing:
            base = {k: existing[k] for k in keys if k in existing}
            subset = {**base, **subset}
            if not subset:
                continue
        saved.update(validate_and_save_field_values(user_id, role_id, subset))
    unknown = set(values) - routed
    if unknown:
        raise HTTPException(
            status_code=400, detail={key: "알 수 없는 필드입니다" for key in sorted(unknown)}
        )
    return saved


def _user_detail(user_id: str, profile: dict | None = None) -> dict:
    profile = profile or _get_profile_or_404(UUID(user_id))
    roles, primary_role_id = _roles_summary(_user_role_rows(user_id))
    admin = get_supabase_admin()
    email = ""
    try:
        resp = admin.auth.admin.get_user_by_id(user_id)
        email = (resp.user.email or "") if resp and resp.user else ""
    except Exception:
        logger.exception("auth 사용자 이메일 조회 실패 user=%s", user_id)
    return {
        **profile,
        "email": email,
        "roles": roles,
        "primary_role_id": primary_role_id,
        "field_values": get_field_values_flat(user_id),
    }


# ------------------------------------------------------------
# 목록·상세 (8.2)
# ------------------------------------------------------------


@router.get("")
def list_users(
    current_user: Annotated[dict, Depends(require_permission(P.USERS_READ))],
    role_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[dict]:
    client = get_supabase_admin()

    query = client.table("user_profiles").select(_PROFILE_COLUMNS).order("name")
    if is_active is not None:
        query = query.eq("is_active", is_active)
    profiles = query.execute().data or []

    if role_id is not None:
        holder_rows = (
            client.table("user_roles").select("user_id").eq("role_id", str(role_id)).execute()
        ).data or []
        holders = {row["user_id"] for row in holder_rows}
        profiles = [p for p in profiles if p["user_id"] in holders]

    if q:
        term = q.strip()
        # 이름 부분일치 + is_searchable 필드값 검색의 합집합 (FR-21)
        matched = {p["user_id"] for p in profiles if term.lower() in (p["name"] or "").lower()}
        field_rows = (
            client.table("role_fields")
            .select("field_key")
            .eq("is_searchable", True)
            .eq("is_active", True)
            .execute()
        ).data or []
        for field_key in sorted({row["field_key"] for row in field_rows}):
            matched.update(search_users_by_field(field_key, term))
        profiles = [p for p in profiles if p["user_id"] in matched]

    user_ids = [p["user_id"] for p in profiles]
    emails = _email_map(set(user_ids))

    role_map: dict[str, list[dict]] = {}
    primary_map: dict[str, str] = {}
    if user_ids:
        role_rows = (
            client.table("user_roles")
            .select(f"user_id, {_ROLE_JOIN}")
            .in_("user_id", user_ids)
            .execute()
        ).data or []
        for row in role_rows:
            role = row.get("roles")
            if not role:
                continue
            role_map.setdefault(row["user_id"], []).append(
                {**role, "is_primary": row["is_primary"]}
            )
            if row["is_primary"]:
                primary_map[row["user_id"]] = role["id"]

    return [
        {
            **p,
            "email": emails.get(p["user_id"], ""),
            "roles": role_map.get(p["user_id"], []),
            "primary_role_id": primary_map.get(p["user_id"]),
        }
        for p in profiles
    ]


@router.get("/{user_id}")
def get_user(
    user_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_READ))],
) -> dict:
    return _user_detail(str(user_id))


# ------------------------------------------------------------
# 계정 발급 (8.1)
# ------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_CREATE))],
) -> dict:
    _fetch_roles_validated(body.role_ids)
    admin = get_supabase_admin()

    temp_password: str | None = None
    try:
        if body.delivery == "invite":
            auth_resp = admin.auth.admin.invite_user_by_email(body.email)
        else:
            temp_password = _generate_temp_password()
            auth_resp = admin.auth.admin.create_user(
                {"email": body.email, "password": temp_password, "email_confirm": True}
            )
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "duplicate" in msg or "exists" in msg or "registered" in msg:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 이메일입니다")
        logger.exception("auth 계정 생성 실패 email=%s delivery=%s", body.email, body.delivery)
        if body.delivery == "invite":
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "초대 메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요"
            )
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "계정 생성 중 오류가 발생했습니다")

    if not auth_resp or not auth_resp.user:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "계정 생성 응답이 올바르지 않습니다")
    new_user_id = auth_resp.user.id

    try:
        admin.table("user_profiles").insert({
            "user_id": new_user_id,
            "name": body.name,
            "must_change_password": body.delivery == "temp_password",
        }).execute()

        admin.table("user_roles").insert([
            {
                "user_id": new_user_id,
                "role_id": str(rid),
                "is_primary": rid == body.primary_role_id,
                "assigned_by": current_user.get("sub"),
            }
            for rid in body.role_ids
        ]).execute()

        _save_field_values_by_role(
            new_user_id, [str(rid) for rid in body.role_ids], body.field_values
        )
    except HTTPException:
        _rollback_auth_user(new_user_id)
        raise
    except Exception:
        logger.exception("계정 발급 실패 (롤백) email=%s", body.email)
        _rollback_auth_user(new_user_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "계정 생성 중 오류가 발생했습니다")

    result = _user_detail(new_user_id)
    result["delivery"] = body.delivery
    if temp_password is not None:
        result["temp_password"] = temp_password
    return result


def _rollback_auth_user(user_id: str) -> None:
    # auth.users 삭제 → user_profiles/user_roles/profile_field_values CASCADE 정리
    try:
        get_supabase_admin().auth.admin.delete_user(user_id)
    except Exception:
        logger.exception("계정 발급 롤백 실패 user=%s (고아 auth 사용자 가능)", user_id)


# ------------------------------------------------------------
# 수정·활성화 (8.2)
# ------------------------------------------------------------


@router.patch("/{user_id}")
def update_user(
    user_id: UUID,
    body: UserUpdate,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_UPDATE))],
) -> dict:
    _get_profile_or_404(user_id)
    update_data = body.model_dump(exclude_unset=True)
    field_values = update_data.pop("field_values", None)
    if not update_data and field_values is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "수정할 항목이 없습니다")

    admin = get_supabase_admin()
    if update_data:
        admin.table("user_profiles").update(update_data).eq("user_id", str(user_id)).execute()

    if field_values:
        role_ids = [row["role_id"] for row in _user_role_rows(str(user_id))]
        _save_field_values_by_role(str(user_id), role_ids, field_values, merge_existing=True)

    return _user_detail(str(user_id))


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_DEACTIVATE))],
) -> dict:
    _get_profile_or_404(user_id)
    if str(user_id) == str(current_user.get("sub")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "본인 계정은 비활성화할 수 없습니다")
    get_supabase_admin().table("user_profiles").update({"is_active": False}).eq(
        "user_id", str(user_id)
    ).execute()
    return {"user_id": str(user_id), "is_active": False}


@router.post("/{user_id}/activate")
def activate_user(
    user_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_DEACTIVATE))],
) -> dict:
    _get_profile_or_404(user_id)
    get_supabase_admin().table("user_profiles").update({"is_active": True}).eq(
        "user_id", str(user_id)
    ).execute()
    return {"user_id": str(user_id), "is_active": True}


# ------------------------------------------------------------
# 역할 부여·회수 (8.3)
# ------------------------------------------------------------


@router.put("/{user_id}/roles")
def replace_user_roles(
    user_id: UUID,
    body: UserRolesUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(require_permission(P.USERS_UPDATE))],
) -> dict:
    _get_profile_or_404(user_id)
    _fetch_roles_validated(body.role_ids)
    client = get_supabase_admin()
    uid = str(user_id)

    current_rows = (
        client.table("user_roles").select("role_id, is_primary").eq("user_id", uid).execute()
    ).data or []
    current_ids = {row["role_id"] for row in current_rows}
    requested_ids = {str(rid) for rid in body.role_ids}
    current_primary = next((r["role_id"] for r in current_rows if r["is_primary"]), None)

    # 마지막 관리자 보호 — 관리자 역할을 회수하는 경우에만 검사 (8.3 AC)
    if ROLE_ADMIN_ID in current_ids and ROLE_ADMIN_ID not in requested_ids:
        assert_not_last_admin(uid)

    to_remove = current_ids - requested_ids
    to_add = requested_ids - current_ids

    if to_remove:
        client.table("user_roles").delete().eq("user_id", uid).in_(
            "role_id", sorted(to_remove)
        ).execute()
    # primary 재지정: 부분 유니크 인덱스(uq_user_roles_primary) 충돌 방지를 위해 선-해제
    if current_primary and current_primary != str(body.primary_role_id):
        client.table("user_roles").update({"is_primary": False}).eq("user_id", uid).eq(
            "is_primary", True
        ).execute()
    if to_add:
        client.table("user_roles").insert([
            {
                "user_id": uid,
                "role_id": rid,
                "is_primary": False,
                "assigned_by": current_user.get("sub"),
            }
            for rid in sorted(to_add)
        ]).execute()
    client.table("user_roles").update({"is_primary": True}).eq("user_id", uid).eq(
        "role_id", str(body.primary_role_id)
    ).execute()

    invalidate_user_permissions(uid)  # 권한 변경 즉시 반영 (AD-11)

    actor = str(current_user.get("sub"))
    logger.info("역할 변경 target=%s by=%s +%d -%d", uid, actor, len(to_add), len(to_remove))
    background_tasks.add_task(_log_role_change, actor, uid, _client_ip(request))

    roles, primary_role_id = _roles_summary(_user_role_rows(uid))
    return {"user_id": uid, "roles": roles, "primary_role_id": primary_role_id}


# ------------------------------------------------------------
# 비밀번호 초기화 (8.2)
# ------------------------------------------------------------


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: UUID,
    current_user: Annotated[dict, Depends(require_permission(P.PASSWORD_RESET_OTHERS))],
) -> dict:
    _get_profile_or_404(user_id)
    admin = get_supabase_admin()
    temp_password = _generate_temp_password()
    try:
        admin.auth.admin.update_user_by_id(str(user_id), {"password": temp_password})
    except Exception:
        logger.exception("비밀번호 초기화 실패 user=%s", user_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "비밀번호 초기화에 실패했습니다")
    admin.table("user_profiles").update({"must_change_password": True}).eq(
        "user_id", str(user_id)
    ).execute()
    return {"user_id": str(user_id), "temp_password": temp_password}
