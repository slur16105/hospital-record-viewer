"""Story 10.4 — 노코드 신규 역할 발급 E2E (SM-1 핵심 성공 지표).

시나리오: 관리자가 **코드 수정 없이** API만으로
  역할 생성 → 권한 부여 → 커스텀 필드 정의 → 계정 발급(임시비번)
  → is_unique 검증 → 신규 역할 로그인 → 권한 경계 확인
을 완주할 수 있는지 배포 백엔드 + 실제 Supabase를 상대로 검증한다.

- conftest.py 의 admin_token / base_url / supabase_config 픽스처를 재사용한다.
- teardown(정리)은 Supabase service_role 로 직접 수행한다 — 시나리오(1~8단계)
  자체는 전부 백엔드 공개 API만 사용한다.
- 테스트 시작 전에도 동일 정리 루틴을 돌려 이전 실행 잔재를 제거한다(재실행 안전).
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from .conftest import auth_headers

ROLE_NAME = "간호사-e2e"
FIELD_KEY = "nurse_license"
LICENSE_VALUE = "NE2E-001"
NURSE_EMAIL = "nurse-e2e@hospital.test"
NURSE_DUP_EMAIL = "nurse-e2e-dup@hospital.test"
GRANTED_CODES = {"records:read_assigned", "departments:read"}

# 단계 간 공유 상태 (파일 내 테스트는 정의 순서대로 실행된다)
S: dict = {}


# ------------------------------------------------------------
# service_role 정리용 헬퍼 (teardown 전용 — 시나리오에는 미사용)
# ------------------------------------------------------------


def _load_env_from_dotenv() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


@pytest.fixture(scope="module")
def service_config() -> dict[str, str]:
    dotenv = _load_env_from_dotenv()
    url = os.environ.get("SUPABASE_URL") or dotenv.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or dotenv.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 미설정 — E2E 건너뜀")
    return {"url": url.rstrip("/"), "key": key}


def _svc_headers(svc: dict[str, str]) -> dict[str, str]:
    return {"apikey": svc["key"], "Authorization": f"Bearer {svc['key']}"}


def _find_auth_user_id(svc: dict[str, str], email: str) -> str | None:
    """GoTrue admin 페이지네이션으로 이메일 → user id 조회."""
    page, per_page = 1, 200
    while page <= 25:
        resp = httpx.get(
            f"{svc['url']}/auth/v1/admin/users",
            params={"page": page, "per_page": per_page},
            headers=_svc_headers(svc),
            timeout=20.0,
        )
        resp.raise_for_status()
        body = resp.json()
        users = body.get("users", body if isinstance(body, list) else [])
        for u in users:
            if (u.get("email") or "").lower() == email.lower():
                return u["id"]
        if len(users) < per_page:
            return None
        page += 1
    return None


def _delete_auth_user(svc: dict[str, str], user_id: str) -> None:
    httpx.delete(
        f"{svc['url']}/auth/v1/admin/users/{user_id}",
        headers=_svc_headers(svc),
        timeout=20.0,
    )


def _rest_rows(svc: dict[str, str], table: str, filters: dict[str, str]) -> list[dict]:
    resp = httpx.get(
        f"{svc['url']}/rest/v1/{table}",
        params={**filters, "select": "*"},
        headers=_svc_headers(svc),
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def _find_role_id(svc: dict[str, str], name: str) -> str | None:
    rows = _rest_rows(svc, "roles", {"name": f"eq.{name}"})
    return rows[0]["id"] if rows else None


def _cleanup(svc: dict[str, str]) -> None:
    """잔재 완전 정리 — 몇 번을 불러도 안전(멱등).

    순서: auth 사용자 삭제(→ user_profiles/user_roles/profile_field_values CASCADE)
          → 역할 삭제(→ role_permissions/role_fields CASCADE).
    """
    for email in (NURSE_EMAIL, NURSE_DUP_EMAIL):
        uid = _find_auth_user_id(svc, email)
        if uid:
            _delete_auth_user(svc, uid)
    role_id = _find_role_id(svc, ROLE_NAME)
    if role_id:
        # 혹시 남은 보유자(user_roles RESTRICT)가 있으면 먼저 제거
        httpx.delete(
            f"{svc['url']}/rest/v1/user_roles",
            params={"role_id": f"eq.{role_id}"},
            headers=_svc_headers(svc),
            timeout=20.0,
        )
        httpx.delete(
            f"{svc['url']}/rest/v1/roles",
            params={"id": f"eq.{role_id}"},
            headers=_svc_headers(svc),
            timeout=20.0,
        )


@pytest.fixture(scope="module", autouse=True)
def e2e_lifecycle(service_config: dict[str, str]):
    """모듈 시작 전 사전 정리 + 종료 시(실패 포함) 최종 정리 보장."""
    _cleanup(service_config)
    yield
    _cleanup(service_config)


def _require(key: str):
    if key not in S:
        pytest.skip(f"선행 단계 실패로 건너뜀 (missing: {key})")
    return S[key]


# ------------------------------------------------------------
# 1. 역할 생성
# ------------------------------------------------------------


def test_step1_create_role(client: httpx.Client, admin_token: str):
    resp = client.post(
        "/api/roles",
        json={"name": ROLE_NAME, "description": "E2E 검증용 간호사 역할"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == ROLE_NAME
    assert body["is_system"] is False
    S["role_id"] = body["id"]


# ------------------------------------------------------------
# 2. 권한 부여 (records:read_assigned + departments:read)
# ------------------------------------------------------------


def test_step2_grant_permissions(client: httpx.Client, admin_token: str):
    role_id = _require("role_id")
    resp = client.get("/api/permissions", headers=auth_headers(admin_token))
    assert resp.status_code == 200, resp.text
    by_code = {p["code"]: p["id"] for p in resp.json()}
    missing = GRANTED_CODES - set(by_code)
    assert not missing, f"권한 카탈로그에 없음: {missing}"

    permission_ids = [by_code[c] for c in sorted(GRANTED_CODES)]
    resp = client.put(
        f"/api/roles/{role_id}/permissions",
        json={"permission_ids": permission_ids},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["permission_ids"]) == set(permission_ids)


# ------------------------------------------------------------
# 3. 커스텀 필드 정의 (nurse_license — text, required, unique)
# ------------------------------------------------------------


def test_step3_define_field(client: httpx.Client, admin_token: str):
    role_id = _require("role_id")
    resp = client.post(
        f"/api/roles/{role_id}/fields",
        json={
            "field_key": FIELD_KEY,
            "label": "간호사 면허번호",
            "field_type": "text",
            "is_required": True,
            "is_unique": True,
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["field_key"] == FIELD_KEY
    assert body["is_required"] is True
    assert body["is_unique"] is True


# ------------------------------------------------------------
# 4. 계정 발급 (temp_password) → 임시 비밀번호 획득
# ------------------------------------------------------------


def test_step4_issue_account(client: httpx.Client, admin_token: str):
    role_id = _require("role_id")
    resp = client.post(
        "/api/users",
        json={
            "email": NURSE_EMAIL,
            "name": "간호사 E2E",
            "role_ids": [role_id],
            "primary_role_id": role_id,
            "delivery": "temp_password",
            "field_values": {FIELD_KEY: LICENSE_VALUE},
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body.get("temp_password"), "temp_password 미반환"
    assert body["field_values"].get(FIELD_KEY) == LICENSE_VALUE
    assert body["must_change_password"] is True
    assert [r["id"] for r in body["roles"]] == [role_id]
    S["nurse_user_id"] = body["user_id"]
    S["temp_password"] = body["temp_password"]


# ------------------------------------------------------------
# 5. is_unique 검증 — 같은 면허번호 재사용 시 400
# ------------------------------------------------------------


def test_step5_unique_license_rejected(
    client: httpx.Client, admin_token: str, service_config: dict[str, str]
):
    role_id = _require("role_id")
    _require("nurse_user_id")
    resp = client.post(
        "/api/users",
        json={
            "email": NURSE_DUP_EMAIL,
            "name": "간호사 중복",
            "role_ids": [role_id],
            "primary_role_id": role_id,
            "delivery": "temp_password",
            "field_values": {FIELD_KEY: LICENSE_VALUE},
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400, resp.text
    assert FIELD_KEY in str(resp.json().get("detail", ""))
    # 실패한 발급은 롤백되어 고아 auth 사용자가 남지 않아야 한다
    assert _find_auth_user_id(service_config, NURSE_DUP_EMAIL) is None


# ------------------------------------------------------------
# 6. 신규 역할 계정 로그인 (임시비번) — 토큰 유효 확인
# ------------------------------------------------------------


def test_step6_nurse_login(supabase_config: dict[str, str]):
    _require("nurse_user_id")
    temp_password = _require("temp_password")
    resp = httpx.post(
        f"{supabase_config['url']}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": supabase_config["anon_key"], "Content-Type": "application/json"},
        json={"email": NURSE_EMAIL, "password": temp_password},
        timeout=15.0,
    )
    assert resp.status_code == 200, f"임시비번 로그인 실패: {resp.text[:200]}"
    token = resp.json()["access_token"]
    assert token
    S["nurse_token"] = token


# ------------------------------------------------------------
# 7. 권한 경계 — 부여한 것만 200, 나머지는 403
# ------------------------------------------------------------


def test_step7_permission_boundaries(client: httpx.Client):
    token = _require("nurse_token")
    headers = auth_headers(token)

    # departments:read 보유 → 200
    resp = client.get("/api/departments", headers=headers)
    assert resp.status_code == 200, resp.text

    # 미보유 권한 → 전부 403
    assert client.get("/api/users", headers=headers).status_code == 403
    assert client.get("/api/roles", headers=headers).status_code == 403
    resp = client.post(
        "/api/medical-records",
        json={"patient_user_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


# ------------------------------------------------------------
# 8. /api/me — permissions가 정확히 부여한 2개인지
# ------------------------------------------------------------


def test_step8_me_reflects_granted_permissions(client: httpx.Client):
    token = _require("nurse_token")
    resp = client.get("/api/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["permissions"]) == GRANTED_CODES
    assert body["primary_role"] == ROLE_NAME
    assert body["profile"]["field_values"].get(FIELD_KEY) == LICENSE_VALUE


# ------------------------------------------------------------
# 9. teardown — 계정 삭제 → cascade 확인 → 역할 삭제(공개 API)
# ------------------------------------------------------------


def test_step9_teardown_and_cascade(
    client: httpx.Client, admin_token: str, service_config: dict[str, str]
):
    role_id = _require("role_id")
    nurse_user_id = _require("nurse_user_id")

    # 간호사 계정 삭제 (auth admin)
    _delete_auth_user(service_config, nurse_user_id)
    assert _find_auth_user_id(service_config, NURSE_EMAIL) is None

    # cascade 확인: user_roles / profile_field_values / user_profiles 잔재 없음
    assert _rest_rows(service_config, "user_roles", {"user_id": f"eq.{nurse_user_id}"}) == []
    assert (
        _rest_rows(service_config, "profile_field_values", {"user_id": f"eq.{nurse_user_id}"})
        == []
    )
    assert _rest_rows(service_config, "user_profiles", {"user_id": f"eq.{nurse_user_id}"}) == []

    # 역할 삭제는 공개 API로 (보유자 없음 → 204)
    resp = client.delete(f"/api/roles/{role_id}", headers=auth_headers(admin_token))
    assert resp.status_code == 204, resp.text
    resp = client.get(f"/api/roles/{role_id}", headers=auth_headers(admin_token))
    assert resp.status_code == 404
