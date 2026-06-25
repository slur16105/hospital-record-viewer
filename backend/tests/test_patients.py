import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_patients_returns_200(client, admin_token):
    """patients → user_profiles 임베드 조인 (migration 00009 FK) 회귀 방어."""
    resp = client.get("/api/patients", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
def test_patient_item_structure(client, admin_token):
    resp = client.get("/api/patients", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    if data:
        item = data[0]
        assert {"id", "user_id", "birth_date", "phone"} <= set(item.keys())
