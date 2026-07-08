from __future__ import annotations

import pytest

from .conftest import auth_headers

# ─────────────────────────────────────────────────────────────
# 유닛 테스트 (네트워크 불필요 — create_client는 객체만 만들고 쿼리 전엔 통신 안 함).
# 앱 모듈 import는 함수 내부에서 지연 로드.
# ─────────────────────────────────────────────────────────────

def test_admin_client_is_singleton():
    from core.database import get_supabase_admin
    assert get_supabase_admin() is get_supabase_admin()


def test_anon_client_is_singleton():
    from core.database import get_supabase
    assert get_supabase() is get_supabase()


def test_user_client_is_not_shared():
    # 토큰별 클라이언트는 .auth()로 변형되므로 절대 공유하면 안 된다 (토큰 격리).
    from core.database import get_supabase_for_user
    a = get_supabase_for_user("token-a")
    b = get_supabase_for_user("token-b")
    assert a is not b


# ─────────────────────────────────────────────────────────────
# 통합 회귀 (배포된 백엔드). async→def 전환 후 인증/권한 응답 불변.
# ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_auth_flow_unaffected_after_refactor(client, admin_token, patient_token):
    assert client.get("/api/patients", headers=auth_headers(admin_token)).status_code == 200
    assert client.get("/api/patients", headers=auth_headers(patient_token)).status_code == 403
