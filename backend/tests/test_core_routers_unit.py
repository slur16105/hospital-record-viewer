"""Story 7.2~7.4 · 8.1~8.3 코어 라우터 순수 단위 테스트 — DB·네트워크 없이 돈다.

- main.app import + 라우트 등록 검증
- 모든 신규 엔드포인트가 올바른 require_permission 코드를 선언하는지
  (FastAPI dependant 인트로스펙션 — AD-6·AD-10 회귀 방어)
- pydantic 요청 모델 검증 (roles.py / users.py)
- invalidate_all_permissions 전체 캐시 무효화

실행: cd backend && /usr/bin/python3 -m pytest tests/test_core_routers_unit.py -v
"""
from __future__ import annotations

import typing
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from core import authz
from core.field_values import FIELD_TYPE_COLUMNS
from core.permissions import P
from main import app
from models.roles import (
    RoleCreate,
    RoleFieldCreate,
    RoleFieldUpdate,
    RolePermissionsUpdate,
    RoleUpdate,
)
from models.users import UserCreate, UserRolesUpdate, UserUpdate

# ------------------------------------------------------------
# 라우트 → 권한 코드 인트로스펙션
# ------------------------------------------------------------

EXPECTED_PERMISSIONS = {
    # roles.py (7.2~7.4)
    ("GET", "/api/roles"): P.ROLES_READ,
    ("POST", "/api/roles"): P.ROLES_MANAGE,
    ("GET", "/api/roles/{role_id}"): P.ROLES_READ,
    ("PATCH", "/api/roles/{role_id}"): P.ROLES_MANAGE,
    ("DELETE", "/api/roles/{role_id}"): P.ROLES_MANAGE,
    ("GET", "/api/permissions"): P.ROLES_READ,
    ("PUT", "/api/roles/{role_id}/permissions"): P.ROLES_MANAGE,
    ("GET", "/api/roles/{role_id}/fields"): P.ROLES_READ,
    ("POST", "/api/roles/{role_id}/fields"): P.ROLES_MANAGE,
    ("PATCH", "/api/roles/{role_id}/fields/{field_id}"): P.ROLES_MANAGE,
    # users.py (8.1~8.3)
    ("GET", "/api/users"): P.USERS_READ,
    ("POST", "/api/users"): P.USERS_CREATE,
    ("GET", "/api/users/{user_id}"): P.USERS_READ,
    ("PATCH", "/api/users/{user_id}"): P.USERS_UPDATE,
    ("POST", "/api/users/{user_id}/deactivate"): P.USERS_DEACTIVATE,
    ("POST", "/api/users/{user_id}/activate"): P.USERS_DEACTIVATE,
    ("PUT", "/api/users/{user_id}/roles"): P.USERS_UPDATE,
    ("POST", "/api/users/{user_id}/reset-password"): P.PASSWORD_RESET_OTHERS,
}


def _declared_permission(route: APIRoute) -> str | None:
    """라우트 의존성 중 require_permission 클로저의 code 프리변수를 추출."""
    for dep in route.dependant.dependencies:
        call = dep.call
        if call is None or getattr(call, "__qualname__", "").split(".")[0] != "require_permission":
            continue
        freevars = call.__code__.co_freevars
        if "code" in freevars and call.__closure__:
            return call.__closure__[freevars.index("code")].cell_contents
    return None


def _actual_permission_map() -> dict:
    actual = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        code = _declared_permission(route)
        if code is None:
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            actual[(method, route.path)] = code
    return actual


def test_app_registers_all_core_routes():
    actual = _actual_permission_map()
    missing = set(EXPECTED_PERMISSIONS) - set(actual)
    assert not missing, f"require_permission 미선언 라우트: {sorted(missing)}"


@pytest.mark.parametrize(("key", "expected_code"), sorted(EXPECTED_PERMISSIONS.items()))
def test_route_declares_expected_permission(key, expected_code):
    actual = _actual_permission_map()
    assert actual.get(key) == expected_code, key


def test_no_role_name_branching_in_core_routers():
    """AD-10: 역할명 문자열 판정 금지 (레거시 컬럼 매핑 주석 블록 제외)."""
    import inspect
    from routers import roles as roles_router, users as users_router

    for module in (roles_router, users_router):
        source = inspect.getsource(module)
        assert 'role == "' not in source and "role == '" not in source, module.__name__


# ------------------------------------------------------------
# pydantic 모델 — roles
# ------------------------------------------------------------


def test_role_create_requires_nonblank_name():
    with pytest.raises(ValidationError):
        RoleCreate(name="   ")
    assert RoleCreate(name=" 코디네이터 ").name == "코디네이터"


def test_role_update_forbids_is_system():
    with pytest.raises(ValidationError):
        RoleUpdate(is_system=True)


def test_role_permissions_update_parses_uuids():
    pid = uuid4()
    assert RolePermissionsUpdate(permission_ids=[pid]).permission_ids == [pid]
    with pytest.raises(ValidationError):
        RolePermissionsUpdate(permission_ids=["not-a-uuid"])


def test_role_field_create_field_type_literal_matches_field_values_mapping():
    """모델 Literal 허용값 == FIELD_TYPE_COLUMNS(=DB enum) — 단일 어휘 회귀 방어."""
    literal_args = set(typing.get_args(RoleFieldCreate.model_fields["field_type"].annotation))
    assert literal_args == set(FIELD_TYPE_COLUMNS)


def test_role_field_create_rejects_unknown_field_type():
    with pytest.raises(ValidationError):
        RoleFieldCreate(field_key="ok_key", label="라벨", field_type="hologram")


@pytest.mark.parametrize("bad_key", ["1abc", "UpperCase", "has space", "한글키", "-dash", ""])
def test_role_field_create_rejects_bad_field_key(bad_key):
    with pytest.raises(ValidationError):
        RoleFieldCreate(field_key=bad_key, label="라벨", field_type="text")


def test_role_field_create_accepts_valid_payload():
    field = RoleFieldCreate(
        field_key="employee_no",
        label="사번",
        field_type="text",
        is_required=True,
        is_unique=True,
        validation={"max_length": 20},
    )
    assert field.sort_order == 0 and field.is_searchable is False


@pytest.mark.parametrize("immutable", [{"field_key": "x"}, {"field_type": "text"}])
def test_role_field_update_forbids_key_and_type_changes(immutable):
    with pytest.raises(ValidationError):
        RoleFieldUpdate(**immutable)


def test_role_field_update_allows_deactivation_only():
    assert RoleFieldUpdate(is_active=False).model_dump(exclude_unset=True) == {
        "is_active": False
    }


# ------------------------------------------------------------
# pydantic 모델 — users
# ------------------------------------------------------------


def _user_create_kwargs(**overrides):
    rid = uuid4()
    base = {
        "email": "new.user@hospital.test",  # 데모 도메인(.test)도 허용되어야 한다
        "name": "신규 사용자",
        "role_ids": [rid],
        "primary_role_id": rid,
        "delivery": "invite",
    }
    base.update(overrides)
    return base


def test_user_create_accepts_valid_invite():
    body = UserCreate(**_user_create_kwargs())
    assert body.delivery == "invite" and body.field_values == {}


def test_user_create_rejects_primary_not_in_role_ids():
    with pytest.raises(ValidationError):
        UserCreate(**_user_create_kwargs(primary_role_id=uuid4()))


def test_user_create_rejects_unknown_delivery():
    with pytest.raises(ValidationError):
        UserCreate(**_user_create_kwargs(delivery="carrier_pigeon"))


def test_user_create_rejects_empty_or_duplicate_roles():
    with pytest.raises(ValidationError):
        UserCreate(**_user_create_kwargs(role_ids=[]))
    rid = uuid4()
    with pytest.raises(ValidationError):
        UserCreate(**_user_create_kwargs(role_ids=[rid, rid], primary_role_id=rid))


def test_user_create_rejects_bad_email():
    with pytest.raises(ValidationError):
        UserCreate(**_user_create_kwargs(email="not-an-email"))


def test_user_update_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        UserUpdate(is_active=False)  # 활성화는 전용 엔드포인트로만
    assert UserUpdate(name="이름").name == "이름"


def test_user_roles_update_requires_primary_in_role_ids():
    rid = uuid4()
    body = UserRolesUpdate(role_ids=[rid], primary_role_id=rid)
    assert body.primary_role_id == rid
    with pytest.raises(ValidationError):
        UserRolesUpdate(role_ids=[rid], primary_role_id=uuid4())


# ------------------------------------------------------------
# invalidate_all_permissions (authz 추가분)
# ------------------------------------------------------------


def test_invalidate_all_permissions_clears_every_user(monkeypatch):
    calls = {"count": 0}

    def fake_fetch(user_id: str):
        calls["count"] += 1
        return frozenset({P.USERS_READ})

    monkeypatch.setattr(authz, "_fetch_user_permissions", fake_fetch)
    with authz._cache_lock:
        authz._cache.clear()

    authz.get_user_permissions("u1")
    authz.get_user_permissions("u2")
    assert calls["count"] == 2

    authz.invalidate_all_permissions()
    authz.get_user_permissions("u1")
    authz.get_user_permissions("u2")
    assert calls["count"] == 4

    with authz._cache_lock:
        authz._cache.clear()
