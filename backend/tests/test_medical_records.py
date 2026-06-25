import pytest

from .conftest import auth_headers


@pytest.mark.integration
def test_list_medical_records_returns_paged(client, doctor_token):
    """의사 토큰으로 진료기록 목록 — RLS 적용된 페이지 응답."""
    resp = client.get("/api/medical-records", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    body = resp.json()
    assert {"data", "total", "page", "page_size"} <= set(body.keys())
    assert isinstance(body["data"], list)


@pytest.mark.integration
def test_medical_records_pagination(client, doctor_token):
    resp = client.get(
        "/api/medical-records",
        params={"page": 1, "page_size": 10},
        headers=auth_headers(doctor_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["data"]) <= 10


@pytest.mark.integration
def test_medical_records_requires_auth(client):
    resp = client.get("/api/medical-records")
    assert resp.status_code == 401
