"""인가 계층 (AD-6·AD-10·AD-11) — Story 6.2.

- 유효 권한 = user_roles ⋈ role_permissions ⋈ permissions 합집합.
- 인메모리 TTL 캐시(60초) — 역할·권한 변경은 60초 이내 반영이면 충분(NFR-8).
  역할 변경 시점에는 invalidate_user_permissions()로 즉시 무효화한다(8.3).
- JWT에 권한을 굽지 않는다 — 토큰 수명 동안 회수 불가능해지기 때문.
- 엔드포인트 선언: `Depends(require_permission(P.RECORDS_CREATE))` (모든 보호 엔드포인트 필수).
"""
from __future__ import annotations

import logging
import threading
import time

from fastapi import Depends, HTTPException, Request, status

from .auth import get_current_user
from .database import get_supabase_admin
from .permissions import ROLE_ADMIN_ID

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# 권한 집합 TTL 캐시 (AD-11 — 단일 인스턴스인 동안 인메모리로 충분)
# ------------------------------------------------------------

PERMISSIONS_CACHE_TTL = 60.0  # 초 (AD-11: ≤60s)

_cache: dict[str, tuple[float, frozenset[str]]] = {}
_cache_lock = threading.Lock()


def _fetch_user_permissions(user_id: str) -> frozenset[str]:
    """DB에서 유효 권한 합집합을 계산한다 (캐시 미적용 — 직접 호출 금지)."""
    client = get_supabase_admin()
    role_rows = (
        client.table("user_roles").select("role_id").eq("user_id", user_id).execute()
    ).data or []
    role_ids = [row["role_id"] for row in role_rows]
    if not role_ids:
        return frozenset()
    perm_rows = (
        client.table("role_permissions")
        .select("permissions(code)")
        .in_("role_id", role_ids)
        .execute()
    ).data or []
    return frozenset(
        row["permissions"]["code"] for row in perm_rows if row.get("permissions")
    )


def get_user_permissions(user_id: str) -> frozenset[str]:
    """사용자의 유효 권한 집합 (보유 역할 권한의 합집합). TTL 60초 캐시."""
    user_id = str(user_id)
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(user_id)
        if entry is not None and entry[0] > now:
            return entry[1]
    permissions = _fetch_user_permissions(user_id)  # DB 호출은 락 밖에서
    with _cache_lock:
        _cache[user_id] = (now + PERMISSIONS_CACHE_TTL, permissions)
    return permissions


def invalidate_user_permissions(user_id: str) -> None:
    """역할 부여·회수 직후 호출 — 해당 사용자의 캐시를 즉시 무효화한다."""
    with _cache_lock:
        _cache.pop(str(user_id), None)


def invalidate_all_permissions() -> None:
    """역할↔권한 조합 변경 직후 호출 — 전체 캐시를 무효화한다 (7.3).

    역할 보유자 목록 조회 없이 단순 전체 클리어. 캐시는 60초 TTL이라
    비용은 다음 요청의 재계산 한 번뿐이다.
    """
    with _cache_lock:
        _cache.clear()


# ------------------------------------------------------------
# require_permission — FastAPI Depends 팩토리 (AD-6)
# ------------------------------------------------------------


def require_permission(code: str):
    """엔드포인트 인가 선언. 사용: Depends(require_permission(P.USERS_READ)).

    JWT 검증(get_current_user) 후 권한 미보유 시 403 {"detail": ...}.
    반환값: current_user dict + "permissions": frozenset[str].
    동기 함수 → FastAPI가 스레드풀에서 실행(이벤트루프 블로킹 없음).
    """

    def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        sub = current_user.get("sub")
        if not sub:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "권한이 없습니다")
        try:
            permissions = get_user_permissions(sub)
        except Exception:
            # 권한 확인 불가 시 fail-closed (require_admin과 동일 컨벤션)
            logger.exception("권한 조회 실패 user=%s code=%s", sub, code)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="권한 확인에 실패했습니다. 잠시 후 다시 시도해주세요",
            )
        if code not in permissions:
            path = request.url.path.replace("\n", " ").replace("\r", " ")
            logger.warning(
                "권한 거부 method=%s path=%s user=%s required=%s",
                request.method, path, sub, code,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "권한이 없습니다")
        return {**current_user, "permissions": permissions}

    return dependency


# ------------------------------------------------------------
# is_system 역할 보호 유틸
# ------------------------------------------------------------


def assert_role_mutable(role: dict) -> None:
    """is_system 역할의 삭제·핵심권한 회수를 차단한다 (7.x에서 사용).

    role: roles 테이블 행 dict (is_system 포함).
    """
    if role.get("is_system"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "시스템 역할은 삭제하거나 권한을 회수할 수 없습니다",
        )


def assert_not_last_admin(user_id: str) -> None:
    """마지막 관리자 보호 (8.3에서 사용).

    관리자 역할 보유자가 user_id 한 명뿐이면 그 역할 제거를 409로 차단한다.
    """
    client = get_supabase_admin()
    rows = (
        client.table("user_roles")
        .select("user_id")
        .eq("role_id", ROLE_ADMIN_ID)
        .execute()
    ).data or []
    holders = {row["user_id"] for row in rows}
    if str(user_id) in holders and len(holders) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "마지막 관리자의 관리자 역할은 제거할 수 없습니다",
        )
