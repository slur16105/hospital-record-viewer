import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_doctors_returns_200(client, admin_token):
    """doctors → user_profiles 임베드 조인 (migration 00009 FK) 회귀 방어."""
    resp = client.get("/api/doctors", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
def test_doctor_item_structure(client, admin_token):
    resp = client.get("/api/doctors", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    if data:
        item = data[0]
        # 이름은 user_profiles 임베드에서 옴 — 조인이 깨지면 비거나 누락됨
        assert "id" in item
        assert "name" in item
