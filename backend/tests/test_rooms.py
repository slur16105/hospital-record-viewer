import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_rooms_returns_200(client, admin_token):
    resp = client.get("/api/rooms", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
def test_room_item_structure(client, admin_token):
    """RoomOut 은 departments 임베드 조인으로 department_name 을 채운다."""
    resp = client.get("/api/rooms", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    if data:
        item = data[0]
        assert {"id", "room_number", "department_id", "department_name", "is_active"} <= set(item.keys())
        assert isinstance(item["department_name"], str)
