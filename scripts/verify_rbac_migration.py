#!/usr/bin/env python3
"""
RBAC v3 마이그레이션(00010~00012) 무손실 검증 스크립트. (Story 6.1, SM-3)

신·구 스키마 건수를 대조해 표로 출력하고, 불일치가 하나라도 있으면 exit 1.
00013(레거시 제거) 적용 전 최종 확인용으로도 사용한다.

Usage:
  python scripts/verify_rbac_migration.py     # backend/.env 자동 로드
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- backend/.env 로드 (scripts/seed.py와 동일 패턴) ---
env_file = Path(__file__).parent.parent / "backend" / ".env"
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SUPABASE_URL or not SERVICE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 필요 (backend/.env)")
    sys.exit(1)

from supabase import create_client  # noqa: E402

sb = create_client(SUPABASE_URL, SERVICE_KEY)

FIELD_LICENSE = "c0000000-0000-0000-0000-000000000001"
FIELD_DEPT = "c0000000-0000-0000-0000-000000000002"
FIELD_BIRTH = "c0000000-0000-0000-0000-000000000003"
FIELD_PHONE = "c0000000-0000-0000-0000-000000000004"


def count(table: str, **filters) -> int:
    q = sb.table(table).select("*", count="exact", head=True)
    for k, v in filters.items():
        if v is None:
            q = q.is_(k, "null")
        else:
            q = q.eq(k, v)
    return q.execute().count or 0


def not_null_count(table: str, column: str) -> int:
    return (
        sb.table(table)
        .select("*", count="exact", head=True)
        .not_.is_(column, "null")
        .execute()
        .count
        or 0
    )


def try_count(table: str) -> int | None:
    """레거시 테이블 건수 — 00013 적용 후(테이블 부재)에는 None."""
    try:
        return count(table)
    except Exception:
        return None


def try_not_null_count(table: str, column: str) -> int | None:
    """레거시 컬럼 not-null 건수 — 00013 적용 후(컬럼 부재)에는 None."""
    try:
        return not_null_count(table, column)
    except Exception:
        return None


checks: list[tuple[str, int, int]] = []  # (설명, 기대, 실제)
skipped: list[str] = []  # 00013 적용 후 레거시 부재로 N/A 처리된 항목

n_profiles = count("user_profiles")
n_doctors = try_count("doctors")     # 00013 이후 None (레거시 테이블 삭제)
n_patients = try_count("patients")   # 00013 이후 None
n_records = count("medical_records")
n_logs = count("access_logs")

# 1) 역할 이관: 모든 사용자에게 user_roles 존재
checks.append(("user_roles ≥ user_profiles", n_profiles, count("user_roles")))
# 2) 기본 역할: primary 보유자 수 = 사용자 수
checks.append(("is_primary 역할 보유자", n_profiles, count("user_roles", is_primary=True)))
# 3) 의사 필드값 — 레거시 doctors 대조는 00013 적용 전에만 가능
if n_doctors is not None:
    checks.append(("의사 면허번호 필드값", n_doctors, count("profile_field_values", role_field_id=FIELD_LICENSE)))
    checks.append(("의사 소속과 필드값", n_doctors, count("profile_field_values", role_field_id=FIELD_DEPT)))
else:
    skipped += ["의사 면허번호 필드값", "의사 소속과 필드값"]
# 4) 환자 필드값 — 레거시 patients 대조는 00013 적용 전에만 가능
if n_patients is not None:
    checks.append(("환자 생년월일 필드값", n_patients, count("profile_field_values", role_field_id=FIELD_BIRTH)))
    checks.append(("환자 연락처 필드값", n_patients, count("profile_field_values", role_field_id=FIELD_PHONE)))
else:
    skipped += ["환자 생년월일 필드값", "환자 연락처 필드값"]
# 5) 진료기록 신 FK 채움
checks.append(("records.patient_user_id 채움", n_records, not_null_count("medical_records", "patient_user_id")))
checks.append(("records.doctor_user_id 채움", n_records, not_null_count("medical_records", "doctor_user_id")))
# 6) 접근로그 resource 소급 — 레거시 record_id 컬럼이 있을 때만 대조 가능
n_logs_with_record = try_not_null_count("access_logs", "record_id")
if n_logs_with_record is not None:
    checks.append(("logs.resource_id 채움", n_logs_with_record, not_null_count("access_logs", "resource_id")))
else:
    skipped.append("logs.resource_id 채움")
# 7) 시드 무결성
checks.append(("권한 카탈로그 16종", 16, count("permissions")))
checks.append(("시드 역할 4종 이상", 4, count("roles")))
checks.append(("role_fields 4종 이상", 4, count("role_fields")))

print(f"\n{'항목':<32} {'기대':>8} {'실제':>8}  판정")
print("-" * 60)
failed = 0
for name, expected, actual in checks:
    # "이상" 항목은 ≥, 나머지는 ==
    ge_ok = name.endswith("이상") or name.startswith("user_roles")
    ok = actual >= expected if ge_ok else actual == expected
    mark = "✅" if ok else "❌"
    if not ok:
        failed += 1
    print(f"{name:<32} {expected:>8} {actual:>8}  {mark}")

for name in skipped:
    print(f"{name:<32} {'—':>8} {'—':>8}  N/A (00013 적용 — 레거시 부재)")

print("-" * 60)
print(f"기준 건수: profiles={n_profiles} doctors={n_doctors} patients={n_patients} "
      f"records={n_records} logs={n_logs}")

if failed:
    print(f"\n❌ {failed}개 항목 불일치 — 00013 적용 금지, 00012 재실행/조사 필요")
    sys.exit(1)
print("\n✅ 전 항목 통과 — 무손실 이관 확인 (SM-3)")
