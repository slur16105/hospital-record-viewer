from __future__ import annotations
import threading
from supabase import create_client, Client
from .config import settings

# service_role 클라이언트는 요청과 무관하고 불변이라 모듈 레벨 싱글톤으로 재사용한다
# (요청마다 새 httpx 세션 생성 방지). 쿼리 빌드는 공유 클라이언트 상태를 변형하지 않으므로
# 스레드풀에서 여러 요청이 동시에 써도 안전하다(supabase/postgrest 2.31 소스로 확인).
# ⚠️ 이 인스턴스에 절대 .postgrest.auth(token)/헤더 등 요청별 상태를 붙이지 말 것
#    — 공유 인스턴스라 사용자 간 세션이 누출된다. 토큰이 필요하면 get_supabase_for_user()를 쓴다.
_admin: Client | None = None
_lock = threading.Lock()


def get_supabase_admin() -> Client:
    global _admin
    if _admin is None:  # 스레드풀 동시 최초 호출 대비 이중검사 락
        with _lock:
            if _admin is None:
                _admin = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _admin


def get_supabase_for_user(token: str) -> Client:
    # 토큰별로 .auth()가 클라이언트를 변형하므로 절대 공유하지 않는다 — 매 호출 새 인스턴스.
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return client
