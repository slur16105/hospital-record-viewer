from __future__ import annotations

import types

import pytest

from .conftest import auth_headers

# ─────────────────────────────────────────────────────────────
# 유닛 테스트 (네트워크 불필요). 앱 모듈 import는 함수 내부에서 지연 로드해
# 의존성 미설치 환경에서도 통합 테스트 수집을 깨뜨리지 않는다.
# ─────────────────────────────────────────────────────────────

def _fake_request(xff: str | None, host: str | None):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    client = types.SimpleNamespace(host=host) if host else None
    return types.SimpleNamespace(headers=headers, client=client)


def test_client_ip_prefers_xff_first_valid():
    from routers.medical_records import _client_ip
    req = _fake_request("203.0.113.7, 10.0.0.1", "10.0.0.1")
    assert _client_ip(req) == "203.0.113.7"


def test_client_ip_falls_back_to_peer_when_no_xff():
    from routers.medical_records import _client_ip
    req = _fake_request(None, "198.51.100.5")
    assert _client_ip(req) == "198.51.100.5"


def test_client_ip_handles_garbage_without_raising():
    from routers.medical_records import _client_ip
    req = _fake_request("not-an-ip", None)
    assert _client_ip(req) is None  # 형식 오류 + 폴백 없음 → None, 예외 없음


def test_cors_origins_filters_invalid():
    from core.config import Settings
    s = Settings(cors_origins="https://ok.com, htp://bad, , https://also.ok")
    assert s.get_cors_origins() == ["https://ok.com", "https://also.ok"]


def test_cors_origins_normalizes_slash_path_and_case():
    from core.config import Settings
    # 끝 슬래시·경로·대문자는 scheme://host 로 정규화되어야 브라우저 Origin과 일치
    s = Settings(cors_origins="https://App.com/, https://x.com/some/path, https://*.wild.com")
    assert s.get_cors_origins() == ["https://app.com", "https://x.com"]


def test_cors_origins_wildcard_passthrough():
    from core.config import Settings
    assert Settings(cors_origins="*").get_cors_origins() == ["*"]


# ─────────────────────────────────────────────────────────────
# 통합 테스트 (배포된 백엔드 대상). 하드닝 후 회귀 없음 + 오류 응답 유출 없음.
# ─────────────────────────────────────────────────────────────

_LEAK_MARKERS = ["supabase", "postgrest", "psycopg", "traceback", "gkcnyilf"]


@pytest.mark.integration
def test_normal_endpoints_unaffected(client, admin_token, patient_token):
    # 정상 권한 흐름이 예외 핸들러 추가 후에도 그대로여야 한다.
    assert client.get("/api/patients", headers=auth_headers(admin_token)).status_code == 200
    assert client.get("/api/patients", headers=auth_headers(patient_token)).status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/api/patients", "/api/doctors", "/api/access-logs", "/api/medical-records"])
def test_error_responses_do_not_leak_internals(client, patient_token, path):
    # 어떤 응답이든(4xx/5xx 포함) 내부 오류 원문/스택/호스트가 새지 않아야 한다.
    resp = client.get(path, headers=auth_headers(patient_token))
    body = resp.text.lower()
    for marker in _LEAK_MARKERS:
        assert marker not in body, f"{path} 응답에 유출 마커 '{marker}' 발견"
