import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_departments_returns_200(client, admin_token):
    resp = client.get("/api/departments", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.integration
def test_department_item_structure(client, admin_token):
    resp = client.get("/api/departments", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    if data:
        item = data[0]
        assert {"id", "name", "is_active"} <= set(item.keys())
        assert isinstance(item["name"], str)
        assert isinstance(item["is_active"], bool)
