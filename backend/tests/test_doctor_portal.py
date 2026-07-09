"""의사 포털 엔드포인트 + 권한 경계 검증 (RBAC v3).

/api/doctor/*는 records:read_assigned / patients:search 권한을 요구한다 —
환자 역할은 records:read_own만 보유하므로 403 (권한 경계, SM-4).
"""
import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_doctor_profile_returns_200_for_doctor(client, doctor_token):
    resp = client.get("/api/doctor/profile", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    body = resp.json()
    assert {"doctor_id", "user_id", "name", "department_id", "department_name", "license_number"} <= set(body.keys())


@pytest.mark.integration
def test_doctor_profile_forbidden_for_patient(client, patient_token):
    """환자 토큰은 records:read_assigned 권한 미보유 → 403 (권한 경계)."""
    resp = client.get("/api/doctor/profile", headers=auth_headers(patient_token))
    assert resp.status_code == 403


@pytest.mark.integration
def test_my_patients_returns_list_for_doctor(client, doctor_token):
    resp = client.get("/api/doctor/my-patients", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
def test_patient_search_returns_list(client, doctor_token):
    resp = client.get(
        "/api/doctor/patients/search",
        params={"name": "홍"},
        headers=auth_headers(doctor_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
def test_doctor_portal_requires_auth(client):
    resp = client.get("/api/doctor/profile")
    assert resp.status_code == 401
