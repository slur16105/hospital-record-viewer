"""Story 6.2·6.3 순수 단위 테스트 — DB·네트워크 없이 돈다.

- 권한 상수(permissions.py) ↔ 00011 시드 code 16종 일치 검증 (AD-10)
- authz TTL 캐시·require_permission 판정 (DB는 monkeypatch로 대체)
- field_values 타입 컬럼 매핑·validation 규칙 해석 (AD-13)

⚠️ 다른 test_*.py는 배포 백엔드 대상 통합 테스트다 — 이 파일만 로컬 단독 실행 가능:
   cd backend && python3 -m pytest tests/test_authz_unit.py -v
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from core import authz
from core.authz import assert_role_mutable, require_permission
from core.field_values import (
    FIELD_TYPE_COLUMNS,
    VALUE_COLUMNS,
    apply_validation_rules,
    build_value_row,
    column_for_field_type,
    validate_field_value,
)
from core.permissions import (
    ALL_PERMISSIONS,
    ROLE_ADMIN_ID,
    ROLE_DOCTOR_ID,
    ROLE_PATIENT_ID,
    ROLE_STAFF_ID,
    SYSTEM_ROLE_IDS,
    P,
)

_MIGRATIONS = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
_SEED_SQL = (_MIGRATIONS / "00011_rbac_seed.sql").read_text(encoding="utf-8")
_SCHEMA_SQL = (_MIGRATIONS / "00010_rbac_core_schema.sql").read_text(encoding="utf-8")


# ------------------------------------------------------------
# AD-10: 권한 상수 ↔ 시드 동기화
# ------------------------------------------------------------


def _seed_permission_codes() -> list[str]:
    """00011의 permissions INSERT 블록에서 code 목록 추출."""
    block = _SEED_SQL.split("INSERT INTO permissions", 1)[1].split("ON CONFLICT", 1)[0]
    return re.findall(r"'b0000000-[0-9a-f-]+',\s*'([a-z_]+:[a-z_]+)'", block)


def test_seed_has_exactly_16_permission_codes():
    assert len(_seed_permission_codes()) == 16


def test_all_permissions_matches_seed_codes_exactly():
    seed_codes = _seed_permission_codes()
    assert set(ALL_PERMISSIONS) == set(seed_codes)
    assert len(ALL_PERMISSIONS) == len(seed_codes) == 16


def test_all_permissions_has_no_duplicates():
    assert len(set(ALL_PERMISSIONS)) == len(ALL_PERMISSIONS)


def test_permission_codes_follow_resource_action_format():
    for code in ALL_PERMISSIONS:
        assert re.fullmatch(r"[a-z_]+:[a-z_]+", code), code


def test_class_constants_are_all_registered():
    class_codes = {
        v for k, v in vars(P).items() if not k.startswith("_") and isinstance(v, str)
    }
    assert class_codes == set(ALL_PERMISSIONS)


def test_role_seed_uuids_match_migration():
    block = _SEED_SQL.split("INSERT INTO roles", 1)[1].split("ON CONFLICT", 1)[0]
    seeded = dict(re.findall(r"\('(a0000000-[0-9a-f-]+)',\s*'([^']+)'", block))
    assert seeded[ROLE_ADMIN_ID] == "관리자"
    assert seeded[ROLE_DOCTOR_ID] == "의사"
    assert seeded[ROLE_PATIENT_ID] == "환자"
    assert seeded[ROLE_STAFF_ID] == "원무과"


def test_admin_is_the_only_system_role_in_seed():
    block = _SEED_SQL.split("INSERT INTO roles", 1)[1].split("ON CONFLICT", 1)[0]
    system_ids = {
        m.group(1)
        for m in re.finditer(r"\('(a0000000-[0-9a-f-]+)',[^)]*?,\s*(true|false)\)", block)
        if m.group(2) == "true"
    }
    assert SYSTEM_ROLE_IDS == system_ids == {ROLE_ADMIN_ID}


# ------------------------------------------------------------
# AD-11: 권한 캐시 (DB는 monkeypatch)
# ------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_permission_cache():
    with authz._cache_lock:
        authz._cache.clear()
    yield
    with authz._cache_lock:
        authz._cache.clear()


@pytest.fixture
def fetch_spy(monkeypatch):
    calls = {"count": 0, "perms": frozenset({P.USERS_READ})}

    def fake_fetch(user_id: str) -> frozenset:
        calls["count"] += 1
        return calls["perms"]

    monkeypatch.setattr(authz, "_fetch_user_permissions", fake_fetch)
    return calls


def test_get_user_permissions_caches_within_ttl(fetch_spy):
    assert authz.get_user_permissions("u1") == {P.USERS_READ}
    assert authz.get_user_permissions("u1") == {P.USERS_READ}
    assert fetch_spy["count"] == 1  # 두 번째 호출은 캐시


def test_get_user_permissions_refetches_after_expiry(fetch_spy, monkeypatch):
    monkeypatch.setattr(authz, "PERMISSIONS_CACHE_TTL", -1.0)  # 즉시 만료
    authz.get_user_permissions("u1")
    authz.get_user_permissions("u1")
    assert fetch_spy["count"] == 2


def test_invalidate_user_permissions_forces_refetch(fetch_spy):
    authz.get_user_permissions("u1")
    authz.invalidate_user_permissions("u1")
    authz.get_user_permissions("u1")
    assert fetch_spy["count"] == 2


def test_cache_is_per_user(fetch_spy):
    authz.get_user_permissions("u1")
    authz.get_user_permissions("u2")
    assert fetch_spy["count"] == 2


# ------------------------------------------------------------
# require_permission 판정
# ------------------------------------------------------------


def _fake_request(path: str = "/api/x") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("test", 80),
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def test_require_permission_grants_and_attaches_permissions(fetch_spy):
    dep = require_permission(P.USERS_READ)
    result = dep(_fake_request(), {"sub": "u1", "email": "a@b.c"})
    assert result["sub"] == "u1"
    assert result["permissions"] == {P.USERS_READ}


def test_require_permission_denies_missing_permission_with_403(fetch_spy):
    dep = require_permission(P.ROLES_MANAGE)
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request(), {"sub": "u1"})
    assert exc.value.status_code == 403


def test_require_permission_denies_token_without_sub(fetch_spy):
    dep = require_permission(P.USERS_READ)
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request(), {})
    assert exc.value.status_code == 403
    assert fetch_spy["count"] == 0


def test_require_permission_fails_closed_on_lookup_error(monkeypatch):
    def boom(user_id: str):
        raise RuntimeError("db down")

    monkeypatch.setattr(authz, "_fetch_user_permissions", boom)
    dep = require_permission(P.USERS_READ)
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request(), {"sub": "u1"})
    assert exc.value.status_code == 503


# ------------------------------------------------------------
# is_system 역할 보호 (순수 로직)
# ------------------------------------------------------------


def test_assert_role_mutable_blocks_system_role():
    with pytest.raises(HTTPException) as exc:
        assert_role_mutable({"id": ROLE_ADMIN_ID, "is_system": True})
    assert exc.value.status_code == 403


def test_assert_role_mutable_allows_normal_role():
    assert_role_mutable({"id": ROLE_DOCTOR_ID, "is_system": False})  # no raise


# ------------------------------------------------------------
# AD-13: typed 컬럼 매핑
# ------------------------------------------------------------


def _enum_field_types() -> set[str]:
    block = _SCHEMA_SQL.split("CREATE TYPE field_type AS ENUM", 1)[1].split(");", 1)[0]
    return set(re.findall(r"'([a-z]+)'", block))


def test_field_type_columns_cover_exactly_the_enum():
    assert set(FIELD_TYPE_COLUMNS) == _enum_field_types()


def test_every_field_type_maps_to_a_valid_value_column():
    for field_type, column in FIELD_TYPE_COLUMNS.items():
        assert column in VALUE_COLUMNS, field_type


def test_column_for_unknown_field_type_raises():
    with pytest.raises(ValueError):
        column_for_field_type("hologram")


@pytest.mark.parametrize(
    ("field_type", "value", "column"),
    [
        ("text", "abc", "value_text"),
        ("phone", "010-1234-5678", "value_text"),
        ("email", "a@b.co", "value_text"),
        ("select", "x", "value_text"),
        ("reference", "a0000000-0000-0000-0000-000000000001", "value_text"),
        ("number", 42, "value_number"),
        ("date", "2026-07-09", "value_date"),
        ("boolean", True, "value_boolean"),
        ("multiselect", ["a"], "value_json"),
        ("json", {"k": 1}, "value_json"),
    ],
)
def test_build_value_row_fills_exactly_one_typed_column(field_type, value, column):
    row = build_value_row("u1", {"id": "f1", "field_type": field_type}, value)
    non_null = [c for c in VALUE_COLUMNS if row[c] is not None]
    assert non_null == [column]
    assert row[column] == value
    assert row["user_id"] == "u1" and row["role_field_id"] == "f1"


def test_build_value_row_none_clears_all_columns():
    row = build_value_row("u1", {"id": "f1", "field_type": "text"}, None)
    assert all(row[c] is None for c in VALUE_COLUMNS)


# ------------------------------------------------------------
# AD-13: validation(json) 규칙 해석
# ------------------------------------------------------------


@pytest.mark.parametrize(
    ("rules", "value", "ok"),
    [
        (None, "anything", True),
        ({}, "anything", True),
        ({"min_length": 3}, "abc", True),
        ({"min_length": 3}, "ab", False),
        ({"max_length": 5}, "abcde", True),
        ({"max_length": 5}, "abcdef", False),
        ({"pattern": r"^\d{4}$"}, "1234", True),
        ({"pattern": r"^\d{4}$"}, "12a4", False),
        ({"min": 1}, 1, True),
        ({"min": 1}, 0, False),
        ({"max": 10}, 10, True),
        ({"max": 10}, 10.5, False),
        ({"min": 0, "max": 150}, 42, True),
    ],
)
def test_apply_validation_rules(rules, value, ok):
    error = apply_validation_rules(rules, value)
    assert (error is None) == ok, error


def test_seed_license_number_rules_are_interpretable():
    # 00011 의사 면허번호 필드: {"max_length": 50}
    assert apply_validation_rules({"max_length": 50}, "L001") is None
    assert apply_validation_rules({"max_length": 50}, "x" * 51) is not None


# ------------------------------------------------------------
# AD-13: field_type별 값 검증
# ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_def", "value", "ok"),
    [
        ({"field_type": "text"}, "hello", True),
        ({"field_type": "text"}, 123, False),
        ({"field_type": "email"}, "a@b.co", True),
        ({"field_type": "email"}, "not-an-email", False),
        ({"field_type": "number"}, 3.14, True),
        ({"field_type": "number"}, "abc", False),
        ({"field_type": "number"}, True, False),  # bool은 숫자가 아님
        ({"field_type": "date"}, "2026-07-09", True),
        ({"field_type": "date"}, "2026-13-40", False),
        ({"field_type": "date"}, "not a date", False),
        ({"field_type": "boolean"}, True, True),
        ({"field_type": "boolean"}, "true", False),
        ({"field_type": "select", "options": {"choices": ["a", "b"]}}, "a", True),
        ({"field_type": "select", "options": {"choices": ["a", "b"]}}, "c", False),
        ({"field_type": "multiselect", "options": {"choices": ["a", "b"]}}, ["a", "b"], True),
        ({"field_type": "multiselect", "options": {"choices": ["a", "b"]}}, ["a", "z"], False),
        ({"field_type": "multiselect"}, "not-a-list", False),
        ({"field_type": "json"}, {"any": "thing"}, True),
        ({"field_type": "json"}, "raw string", False),
        ({"field_type": "reference"}, "some-uuid", True),
        ({"field_type": "reference"}, "", False),
        ({"field_type": "hologram"}, "x", False),
    ],
)
def test_validate_field_value_type_checks(field_def, value, ok):
    _, error = validate_field_value(field_def, value)
    assert (error is None) == ok, error


def test_validate_field_value_coerces_numeric_strings():
    assert validate_field_value({"field_type": "number"}, "42") == (42, None)
    assert validate_field_value({"field_type": "number"}, "3.5") == (3.5, None)


def test_validate_field_value_applies_validation_rules():
    field_def = {"field_type": "text", "validation": {"min_length": 8}}
    _, error = validate_field_value(field_def, "short")
    assert error is not None
    _, error = validate_field_value(field_def, "long enough")
    assert error is None
