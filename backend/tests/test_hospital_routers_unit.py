"""Story 10.1 병원 도메인 라우터 순수 단위 테스트 — DB·네트워크 없이 돈다.

- 병원 도메인 전 보호 엔드포인트의 require_permission/require_any_permission 선언 검증
  (FastAPI dependant 인트로스펙션 — AD-6·AD-10 회귀 방어, test_core_routers_unit 확장판)
- require_any_permission 판정 (DB는 monkeypatch로 대체)
- 역할명 문자열 분기 잔존 0건 (AD-10)

실행: cd backend && /usr/bin/python3 -m pytest tests/test_hospital_routers_unit.py -v
"""
from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from core import authz
from core.authz import require_any_permission
from core.permissions import P
from main import app

# ------------------------------------------------------------
# 라우트 → 권한 코드 인트로스펙션 (require_permission: 단일 code)
# ------------------------------------------------------------

EXPECTED_SINGLE = {
    # medical_records.py
    ("POST", "/api/medical-records"): P.RECORDS_CREATE,
    ("PATCH", "/api/medical-records/{record_id}"): P.RECORDS_UPDATE_OWN,
    # doctor.py (의사 포털)
    ("GET", "/api/doctor/profile"): P.RECORDS_READ_ASSIGNED,
    ("GET", "/api/doctor/my-patients"): P.RECORDS_READ_ASSIGNED,
    ("GET", "/api/doctor/patients/search"): P.PATIENTS_SEARCH,
    # departments.py / rooms.py
    ("GET", "/api/departments"): P.DEPARTMENTS_READ,
    ("POST", "/api/departments"): P.DEPARTMENTS_MANAGE,
    ("PATCH", "/api/departments/{dept_id}"): P.DEPARTMENTS_MANAGE,
    ("GET", "/api/rooms"): P.DEPARTMENTS_READ,
    ("POST", "/api/rooms"): P.DEPARTMENTS_MANAGE,
    ("PATCH", "/api/rooms/{room_id}"): P.DEPARTMENTS_MANAGE,
    # access_logs.py
    ("GET", "/api/access-logs"): P.LOGS_READ,
}

# require_any_permission: 코드 집합 (진료기록 조회 스코프 분기)
EXPECTED_ANY = {
    ("GET", "/api/medical-records"): {
        P.RECORDS_READ_ALL, P.RECORDS_READ_ASSIGNED, P.RECORDS_READ_OWN,
    },
    ("GET", "/api/medical-records/{record_id}"): {
        P.RECORDS_READ_ALL, P.RECORDS_READ_ASSIGNED, P.RECORDS_READ_OWN,
    },
}


def _declared(route: APIRoute):
    """(단일 code | None, any-codes frozenset | None) — 라우터+엔드포인트 의존성 전체 탐색."""
    single = None
    any_codes = None
    for dep in route.dependant.dependencies:
        call = dep.call
        if call is None:
            continue
        owner = getattr(call, "__qualname__", "").split(".")[0]
        freevars = getattr(call.__code__, "co_freevars", ())
        if owner == "require_permission" and "code" in freevars and call.__closure__:
            single = call.__closure__[freevars.index("code")].cell_contents
        elif owner == "require_any_permission" and "codes" in freevars and call.__closure__:
            any_codes = frozenset(call.__closure__[freevars.index("codes")].cell_contents)
    return single, any_codes


def _route_map() -> dict:
    result = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        single, any_codes = _declared(route)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            result[(method, route.path)] = (single, any_codes)
    return result


def test_all_hospital_routes_declare_permission():
    actual = _route_map()
    missing = (set(EXPECTED_SINGLE) | set(EXPECTED_ANY)) - set(actual)
    assert not missing, f"미등록 라우트: {sorted(missing)}"
    undeclared = [
        key for key in (set(EXPECTED_SINGLE) | set(EXPECTED_ANY))
        if actual[key] == (None, None)
    ]
    assert not undeclared, f"require_permission 미선언: {sorted(undeclared)}"


@pytest.mark.parametrize(("key", "expected_code"), sorted(EXPECTED_SINGLE.items()))
def test_route_declares_expected_single_permission(key, expected_code):
    single, _ = _route_map()[key]
    assert single == expected_code, key


@pytest.mark.parametrize(("key", "expected_codes"), sorted(EXPECTED_ANY.items()))
def test_route_declares_expected_any_permission(key, expected_codes):
    _, any_codes = _route_map()[key]
    assert any_codes == frozenset(expected_codes), key


def test_no_unprotected_hospital_routes():
    """/health, /api/me 외 모든 병원·코어 라우트는 권한 선언 필수 (AD-6)."""
    allowed_open = {"/health", "/api/me"}
    for (method, path), (single, any_codes) in _route_map().items():
        if path in allowed_open:
            continue
        assert single or any_codes, f"권한 미선언 라우트: {method} {path}"


# ------------------------------------------------------------
# require_any_permission 판정 (DB monkeypatch)
# ------------------------------------------------------------


def _fake_request() -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/api/medical-records",
        "headers": [], "query_string": b"",
    })


def test_require_any_permission_needs_at_least_one_code():
    with pytest.raises(ValueError):
        require_any_permission()


def test_require_any_permission_passes_with_one_of(monkeypatch):
    monkeypatch.setattr(
        authz, "get_user_permissions", lambda uid: frozenset({P.RECORDS_READ_OWN})
    )
    dep = require_any_permission(P.RECORDS_READ_ALL, P.RECORDS_READ_OWN)
    result = dep(_fake_request(), {"sub": "u1"})
    assert result["permissions"] == frozenset({P.RECORDS_READ_OWN})


def test_require_any_permission_403_when_none_held(monkeypatch):
    monkeypatch.setattr(
        authz, "get_user_permissions", lambda uid: frozenset({P.LOGS_READ})
    )
    dep = require_any_permission(P.RECORDS_READ_ALL, P.RECORDS_READ_OWN)
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request(), {"sub": "u1"})
    assert exc.value.status_code == 403


def test_require_any_permission_503_when_lookup_fails(monkeypatch):
    def boom(uid):
        raise RuntimeError("db down")

    monkeypatch.setattr(authz, "get_user_permissions", boom)
    dep = require_any_permission(P.RECORDS_READ_ALL)
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request(), {"sub": "u1"})
    assert exc.value.status_code == 503


# ------------------------------------------------------------
# AD-10: 역할명 문자열 분기 잔존 0건
# ------------------------------------------------------------


def test_no_role_name_branching_in_hospital_routers():
    from routers import (
        access_logs, departments, doctor,
        hospital_fields, medical_records, rooms,
    )

    for module in (
        access_logs, departments, doctor,
        hospital_fields, medical_records, rooms,
    ):
        source = inspect.getsource(module)
        for pattern in ('role == "', "role == '", '.eq("role"', "get(\"role\") =="):
            assert pattern not in source, f"{module.__name__}: {pattern}"


def test_no_role_name_branching_in_core_auth():
    """require_admin(역할명 판정) 제거 회귀 방어."""
    from core import auth

    source = inspect.getsource(auth)
    assert "require_admin" not in source.replace(
        "require_admin(user_profiles.role 역할명 판정)은 제거됨", ""
    )
    assert '!= "admin"' not in source
