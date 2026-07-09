"""권한 경계(require_permission) 통합 테스트 — RBAC v3 (SM-4).

역할명이 아니라 **권한 코드** 보유 여부로 판정된다 (AD-10):
  - /api/access-logs  → logs:read     (관리자만 보유)
  - /api/users        → users:read    (관리자·원무과 보유, 의사·환자 미보유)
  - 쓰기 계열         → users:create / users:update / password:reset_others

(구 /api/doctors·/api/patients 라우터는 00013 정리에서 제거 — /api/users로 대체)
의사·환자 기본 역할은 위 권한이 없으므로 403이어야 한다.
"""
import pytest

from .conftest import auth_headers

# (path, 필요 권한 코드) — 의사/환자 역할이 보유하지 않는 읽기 권한
PERMISSION_GUARDED_READS = [
    ("/api/access-logs", "logs:read"),
    ("/api/users", "users:read"),
]
_READ_PATHS = [path for path, _ in PERMISSION_GUARDED_READS]

# 쓰기 계열 — (method, path, json body, 필요 권한 코드)
# 가드(require_permission)가 본문 검증보다 먼저 실행되므로 빈 body로 403을 확인할 수 있다.
_DUMMY_ID = "00000000-0000-0000-0000-000000000000"
PERMISSION_GUARDED_WRITES = [
    ("post", "/api/users", {}, "users:create"),
    ("patch", f"/api/users/{_DUMMY_ID}", {}, "users:update"),
    ("post", f"/api/users/{_DUMMY_ID}/reset-password", None, "password:reset_others"),
]


@pytest.mark.integration
@pytest.mark.parametrize("path, permission", PERMISSION_GUARDED_READS)
def test_patient_without_permission_gets_403(client, patient_token, path, permission):
    """환자 역할은 records:read_own만 보유 — 해당 권한 미보유 시 403."""
    resp = client.get(path, headers=auth_headers(patient_token))
    assert resp.status_code == 403, f"{path} ({permission})"
    assert resp.json()["detail"] == "권한이 없습니다"


@pytest.mark.integration
@pytest.mark.parametrize("path, permission", PERMISSION_GUARDED_READS)
def test_doctor_without_permission_gets_403(client, doctor_token, path, permission):
    """의사 역할은 진료 계열 권한만 보유 — users:read/logs:read 미보유 시 403."""
    resp = client.get(path, headers=auth_headers(doctor_token))
    assert resp.status_code == 403, f"{path} ({permission})"
    assert resp.json()["detail"] == "권한이 없습니다"


@pytest.mark.integration
@pytest.mark.parametrize("method, path, body, permission", PERMISSION_GUARDED_WRITES)
def test_patient_without_permission_gets_403_on_writes(
    client, patient_token, method, path, body, permission
):
    resp = getattr(client, method)(path, json=body, headers=auth_headers(patient_token))
    assert resp.status_code == 403, f"{method} {path} ({permission})"
    assert resp.json()["detail"] == "권한이 없습니다"


@pytest.mark.integration
@pytest.mark.parametrize("path", _READ_PATHS)
def test_no_token_gets_401(client, path):
    resp = client.get(path)
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("path", _READ_PATHS)
def test_admin_with_permission_gets_200(client, admin_token, path):
    """관리자 역할은 전체 권한 보유 — 정상 200."""
    resp = client.get(path, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    # 스키마 대강 확인 — access-logs는 페이지 객체, 나머지는 목록
    if path == "/api/access-logs":
        assert {"data", "total"} <= set(body.keys())
    else:
        assert isinstance(body, list)
