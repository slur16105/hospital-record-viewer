import pytest

from .conftest import auth_headers

ADMIN_ONLY_PATHS = ["/api/access-logs", "/api/patients", "/api/doctors"]

# 쓰기 계열 관리자 전용 엔드포인트 — (method, path, json body)
# 가드(require_admin)가 본문 검증보다 먼저 실행되므로 빈 body로 403을 확인할 수 있다.
_DUMMY_ID = "00000000-0000-0000-0000-000000000000"
ADMIN_ONLY_WRITES = [
    ("post", "/api/doctors", {}),
    ("patch", f"/api/doctors/{_DUMMY_ID}", {}),
    ("post", f"/api/doctors/{_DUMMY_ID}/reset-password", None),
    ("patch", f"/api/patients/{_DUMMY_ID}", {}),
]


@pytest.mark.integration
@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_patient_token_gets_403(client, patient_token, path):
    resp = client.get(path, headers=auth_headers(patient_token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "관리자 권한이 필요합니다"


@pytest.mark.integration
@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_doctor_token_gets_403(client, doctor_token, path):
    resp = client.get(path, headers=auth_headers(doctor_token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "관리자 권한이 필요합니다"


@pytest.mark.integration
@pytest.mark.parametrize("method, path, body", ADMIN_ONLY_WRITES)
def test_patient_token_gets_403_on_writes(client, patient_token, method, path, body):
    resp = getattr(client, method)(path, json=body, headers=auth_headers(patient_token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "관리자 권한이 필요합니다"


@pytest.mark.integration
@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_no_token_gets_401(client, path):
    resp = client.get(path)
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_admin_token_still_gets_200(client, admin_token, path):
    resp = client.get(path, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    # 스키마 대강 확인 — access-logs는 페이지 객체, 나머지는 목록
    if path == "/api/access-logs":
        assert {"data", "total"} <= set(body.keys())
    else:
        assert isinstance(body, list)
