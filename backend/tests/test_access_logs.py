import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_access_logs_returns_paged(client, admin_token):
    resp = client.get("/api/access-logs", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert {"data", "total", "page", "page_size"} <= set(body.keys())
    assert isinstance(body["data"], list)
    assert isinstance(body["total"], int)


@pytest.mark.integration
def test_access_logs_pagination_params(client, admin_token):
    resp = client.get(
        "/api/access-logs",
        params={"page": 1, "page_size": 5},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["data"]) <= 5
