"""RBAC 코어 API 통합 테스트 — Story 10.3.

배포 백엔드 + 실제 Supabase를 대상으로 검증한다:
  - GET /api/me                — roles/primary_role/permissions/field_values 계약
  - /api/roles CRUD            — 임시 역할 생성→수정→권한 조합(PUT)→삭제 (teardown 보장)
  - is_system 역할 보호        — 수정·삭제·권한 회수 403
  - /api/users 목록·상세       — 필드값 평탄화(EAV → {field_key: value}) 확인
  - 권한 경계                  — roles:read/roles:manage/users:read 미보유 토큰 403

⚠️ 테스트가 만든 데이터(임시 역할)는 반드시 정리한다 — fixture finalizer로 보장.
"""
from __future__ import annotations

import uuid

import pytest

from .conftest import auth_headers

# 00011 시드 고정 UUID (core/permissions.py와 동기화)
ROLE_ADMIN_ID = "a0000000-0000-0000-0000-000000000001"
ROLE_DOCTOR_ID = "a0000000-0000-0000-0000-000000000002"
ROLE_PATIENT_ID = "a0000000-0000-0000-0000-000000000003"

# 00011 기준 역할별 권한 세트
DOCTOR_PERMISSIONS = {
    "records:create",
    "records:update_own",
    "records:read_assigned",
    "patients:search",
    "departments:read",
}
PATIENT_PERMISSIONS = {"records:read_own"}


# ------------------------------------------------------------
# GET /api/me — 프론트 메뉴·가드의 단일 소스
# ------------------------------------------------------------


@pytest.mark.integration
def test_me_admin_has_full_permission_union(client, admin_token):
    resp = client.get("/api/me", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert {"user", "profile", "roles", "primary_role", "permissions"} <= set(body.keys())
    # 관리자 역할은 전 권한 보유 (00011: role_permissions ← 전체 SELECT)
    perms = set(body["permissions"])
    assert {"roles:manage", "roles:read", "users:read", "logs:read"} <= perms
    assert len(perms) >= 16
    assert body["primary_role"] == "관리자"
    role_ids = {r["id"] for r in body["roles"]}
    assert ROLE_ADMIN_ID in role_ids
    assert isinstance(body["profile"].get("field_values"), dict)


@pytest.mark.integration
def test_me_doctor_permissions_and_field_values(client, doctor_token):
    resp = client.get("/api/me", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["permissions"]) == DOCTOR_PERMISSIONS
    assert body["primary_role"] == "의사"
    # 필드값 평탄화 — 의사 필드(license_number, department_id) 노출 (AD-13)
    field_values = body["profile"]["field_values"]
    assert "license_number" in field_values
    assert "department_id" in field_values


@pytest.mark.integration
def test_me_patient_permissions(client, patient_token):
    resp = client.get("/api/me", headers=auth_headers(patient_token))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["permissions"]) == PATIENT_PERMISSIONS
    assert body["primary_role"] == "환자"
    field_values = body["profile"]["field_values"]
    assert "birth_date" in field_values
    assert "phone" in field_values


@pytest.mark.integration
def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


# ------------------------------------------------------------
# /api/roles — 목록·권한 카탈로그 (roles:read)
# ------------------------------------------------------------


@pytest.mark.integration
def test_list_roles_returns_seeded_roles(client, admin_token):
    resp = client.get("/api/roles", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    roles = resp.json()
    by_id = {r["id"]: r for r in roles}
    assert ROLE_ADMIN_ID in by_id
    assert by_id[ROLE_ADMIN_ID]["is_system"] is True
    assert isinstance(by_id[ROLE_ADMIN_ID]["user_count"], int)
    assert ROLE_DOCTOR_ID in by_id and ROLE_PATIENT_ID in by_id


@pytest.mark.integration
def test_list_permissions_catalog_has_16_codes(client, admin_token):
    resp = client.get("/api/permissions", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    perms = resp.json()
    codes = {p["code"] for p in perms}
    assert len(codes) >= 16
    assert {"roles:manage", "records:read_own", "users:create"} <= codes


# ------------------------------------------------------------
# 임시 역할 라이프사이클 — 생성→수정→권한 PUT→삭제 (teardown 보장)
# ------------------------------------------------------------


@pytest.fixture
def temp_role(client, admin_token):
    """임시 역할 생성 후 테스트 종료 시 반드시 삭제 (이미 삭제됐어도 무해)."""
    name = f"임시역할-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/roles",
        json={"name": name, "description": "통합 테스트용 임시 역할"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    role = resp.json()
    yield role
    # teardown — 권한 조합은 role 삭제 시 CASCADE 정리됨
    client.delete(f"/api/roles/{role['id']}", headers=auth_headers(admin_token))


@pytest.mark.integration
def test_temp_role_create_shape(client, admin_token, temp_role):
    assert temp_role["is_system"] is False
    assert temp_role["user_count"] == 0
    # 상세 조회 — permissions/fields 빈 목록으로 시작
    resp = client.get(f"/api/roles/{temp_role['id']}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["permissions"] == []
    assert detail["fields"] == []


@pytest.mark.integration
def test_temp_role_duplicate_name_409(client, admin_token, temp_role):
    resp = client.post(
        "/api/roles",
        json={"name": temp_role["name"]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.integration
def test_temp_role_update(client, admin_token, temp_role):
    new_name = f"수정역할-{uuid.uuid4().hex[:8]}"
    resp = client.patch(
        f"/api/roles/{temp_role['id']}",
        json={"name": new_name, "description": "수정됨"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == new_name
    assert body["description"] == "수정됨"


@pytest.mark.integration
def test_temp_role_permissions_put_roundtrip(client, admin_token, temp_role):
    """권한 조합 PUT — 부여·교체가 상세 조회에 반영되어야 한다 (7.3)."""
    catalog = client.get("/api/permissions", headers=auth_headers(admin_token)).json()
    by_code = {p["code"]: p["id"] for p in catalog}
    picked = [by_code["roles:read"], by_code["departments:read"]]

    resp = client.put(
        f"/api/roles/{temp_role['id']}/permissions",
        json={"permission_ids": picked},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert set(resp.json()["permission_ids"]) == set(picked)

    detail = client.get(
        f"/api/roles/{temp_role['id']}", headers=auth_headers(admin_token)
    ).json()
    assert {p["code"] for p in detail["permissions"]} == {"roles:read", "departments:read"}

    # 교체 (회수 + 추가) — 비시스템 역할은 자유롭게 회수 가능
    resp = client.put(
        f"/api/roles/{temp_role['id']}/permissions",
        json={"permission_ids": [by_code["departments:read"]]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    detail = client.get(
        f"/api/roles/{temp_role['id']}", headers=auth_headers(admin_token)
    ).json()
    assert {p["code"] for p in detail["permissions"]} == {"departments:read"}


@pytest.mark.integration
def test_temp_role_permissions_put_unknown_id_400(client, admin_token, temp_role):
    resp = client.put(
        f"/api/roles/{temp_role['id']}/permissions",
        json={"permission_ids": ["00000000-0000-0000-0000-00000000dead"]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.integration
def test_temp_role_delete_then_404(client, admin_token):
    """생성→삭제→조회 404 전체 사이클 (fixture 없이 직접 정리)."""
    name = f"삭제역할-{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/roles", json={"name": name}, headers=auth_headers(admin_token)
    )
    assert created.status_code == 201
    role_id = created.json()["id"]
    try:
        resp = client.delete(f"/api/roles/{role_id}", headers=auth_headers(admin_token))
        assert resp.status_code == 204
        resp = client.get(f"/api/roles/{role_id}", headers=auth_headers(admin_token))
        assert resp.status_code == 404
    finally:
        client.delete(f"/api/roles/{role_id}", headers=auth_headers(admin_token))


# ------------------------------------------------------------
# is_system 역할 보호 — 수정·삭제·권한 회수 403
# ------------------------------------------------------------


@pytest.mark.integration
def test_system_role_patch_403(client, admin_token):
    resp = client.patch(
        f"/api/roles/{ROLE_ADMIN_ID}",
        json={"description": "변조 시도"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_system_role_delete_403(client, admin_token):
    resp = client.delete(
        f"/api/roles/{ROLE_ADMIN_ID}", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_system_role_permission_revoke_403(client, admin_token):
    """관리자(시스템) 역할의 권한 회수는 403 — 빈 조합 PUT은 전체 회수 시도다."""
    resp = client.put(
        f"/api/roles/{ROLE_ADMIN_ID}/permissions",
        json={"permission_ids": []},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 403


# ------------------------------------------------------------
# /api/users — 목록·상세, 필드값 평탄화 (users:read)
# ------------------------------------------------------------


@pytest.mark.integration
def test_users_list_shape_and_roles(client, admin_token):
    resp = client.get(
        "/api/users",
        params={"role_id": ROLE_DOCTOR_ID},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    users = resp.json()
    assert users, "의사 역할 보유 사용자가 시드되어 있어야 한다"
    item = users[0]
    assert {"user_id", "name", "email", "roles", "primary_role_id", "is_active"} <= set(item.keys())
    assert any(r["id"] == ROLE_DOCTOR_ID for r in item["roles"])


@pytest.mark.integration
def test_users_detail_flattens_field_values(client, admin_token):
    """상세는 EAV를 {field_key: value}로 평탄화해 노출한다 (AD-13)."""
    users = client.get(
        "/api/users",
        params={"role_id": ROLE_DOCTOR_ID},
        headers=auth_headers(admin_token),
    ).json()
    user_id = users[0]["user_id"]
    resp = client.get(f"/api/users/{user_id}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    detail = resp.json()
    assert isinstance(detail["field_values"], dict)
    assert "license_number" in detail["field_values"]
    assert "department_id" in detail["field_values"]
    assert detail["primary_role_id"] == ROLE_DOCTOR_ID


@pytest.mark.integration
def test_users_search_by_name(client, admin_token):
    resp = client.get(
        "/api/users", params={"q": "김민준"}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert any(u["name"] == "김민준" for u in resp.json())


@pytest.mark.integration
def test_users_detail_unknown_404(client, admin_token):
    resp = client.get(
        "/api/users/00000000-0000-0000-0000-00000000dead",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


# ------------------------------------------------------------
# 권한 경계 — roles:*/users:* 미보유 토큰은 403
# ------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/api/roles", None),                      # roles:read 미보유
        ("get", "/api/permissions", None),                # roles:read 미보유
        ("post", "/api/roles", {"name": "x"}),            # roles:manage 미보유
        ("get", "/api/users", None),                      # users:read 미보유
    ],
)
def test_doctor_token_403_on_core_admin_apis(client, doctor_token, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    resp = client.request(method.upper(), path, headers=auth_headers(doctor_token), **kwargs)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "권한이 없습니다"


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/api/roles", "/api/users"])
def test_patient_token_403_on_core_admin_apis(client, patient_token, path):
    resp = client.get(path, headers=auth_headers(patient_token))
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/api/roles", "/api/users", "/api/permissions"])
def test_core_admin_apis_require_auth(client, path):
    assert client.get(path).status_code == 401
