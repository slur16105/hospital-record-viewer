"""권한 코드 상수 단일 원본 (AD-10).

- 코드 형식: `<resource>:<action>` 소문자 스네이크.
- supabase/migrations/00011_rbac_seed.sql 의 permissions.code 16종과
  **정확히 일치**해야 한다 (회귀 테스트: tests/test_authz_unit.py).
- 시드(scripts/seed.py)·엔드포인트 선언은 반드시 이 상수를 참조한다.
  역할명은 코드 어디에서도 판정 조건으로 쓰지 않는다 (is_system 보호 로직 제외).
"""
from __future__ import annotations


class P:
    """권한 코드 상수. 사용 예: Depends(require_permission(P.RECORDS_CREATE))"""

    # 사용자
    USERS_CREATE = "users:create"
    USERS_READ = "users:read"
    USERS_UPDATE = "users:update"
    USERS_DEACTIVATE = "users:deactivate"
    PASSWORD_RESET_OTHERS = "password:reset_others"

    # 시스템
    ROLES_MANAGE = "roles:manage"
    ROLES_READ = "roles:read"

    # 마스터데이터
    DEPARTMENTS_MANAGE = "departments:manage"
    DEPARTMENTS_READ = "departments:read"

    # 진료기록
    RECORDS_CREATE = "records:create"
    RECORDS_UPDATE_OWN = "records:update_own"
    RECORDS_READ_OWN = "records:read_own"
    RECORDS_READ_ASSIGNED = "records:read_assigned"
    RECORDS_READ_ALL = "records:read_all"
    PATIENTS_SEARCH = "patients:search"

    # 감사
    LOGS_READ = "logs:read"


# 00011 시드의 16개 code 전체 목록 (순서: 시드 UUID 순번)
ALL_PERMISSIONS: tuple[str, ...] = (
    P.USERS_CREATE,
    P.USERS_READ,
    P.USERS_UPDATE,
    P.USERS_DEACTIVATE,
    P.ROLES_MANAGE,
    P.ROLES_READ,
    P.DEPARTMENTS_MANAGE,
    P.DEPARTMENTS_READ,
    P.RECORDS_CREATE,
    P.RECORDS_UPDATE_OWN,
    P.RECORDS_READ_OWN,
    P.RECORDS_READ_ASSIGNED,
    P.RECORDS_READ_ALL,
    P.PATIENTS_SEARCH,
    P.LOGS_READ,
    P.PASSWORD_RESET_OTHERS,
)

# ------------------------------------------------------------
# 역할 시드 UUID (00011_rbac_seed.sql 고정 UUID와 동기화)
# ------------------------------------------------------------

ROLE_ADMIN_ID = "a0000000-0000-0000-0000-000000000001"   # 관리자 (is_system=true)
ROLE_DOCTOR_ID = "a0000000-0000-0000-0000-000000000002"  # 의사
ROLE_PATIENT_ID = "a0000000-0000-0000-0000-000000000003" # 환자
ROLE_STAFF_ID = "a0000000-0000-0000-0000-000000000004"   # 원무과

# is_system=true로 시드되는 역할 — 삭제·핵심권한 회수 불가 (백엔드 강제)
SYSTEM_ROLE_IDS: frozenset[str] = frozenset({ROLE_ADMIN_ID})
