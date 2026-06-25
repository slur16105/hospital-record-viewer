"""
인증 검증 테스트.

회귀 방지 핵심: Supabase가 JWT를 ES256(비대칭)으로 발급하므로 백엔드는 JWKS로
검증해야 한다. 과거 HS256 검증 탓에 유효한 토큰이 전부 401로 거부된 적이 있다.
아래 `test_valid_token_is_accepted` 가 정확히 그 회귀를 방어한다.
"""
import pytest

from .conftest import auth_headers

PROTECTED_ENDPOINT = "/api/departments"


@pytest.mark.integration
def test_no_token_is_rejected(client):
    resp = client.get(PROTECTED_ENDPOINT)
    assert resp.status_code == 401


@pytest.mark.integration
def test_garbage_token_is_rejected(client):
    resp = client.get(PROTECTED_ENDPOINT, headers=auth_headers("not-a-real-jwt"))
    assert resp.status_code == 401


@pytest.mark.integration
def test_malformed_bearer_is_rejected(client):
    resp = client.get(
        PROTECTED_ENDPOINT,
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
def test_valid_token_is_accepted(client, admin_token):
    """ES256 토큰이 JWKS로 정상 검증되어 200을 받아야 한다 (인증 회귀 방어)."""
    resp = client.get(PROTECTED_ENDPOINT, headers=auth_headers(admin_token))
    assert resp.status_code == 200
