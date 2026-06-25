"""
공용 pytest fixture.

이 테스트들은 **통합 테스트**다 — 배포된(또는 로컬) 백엔드와 실제 Supabase Auth를
대상으로 동작한다. 방금 회귀로 잡았던 인증(ES256/JWKS)·데이터 엔드포인트 버그를
직접 방어하는 것이 목적이다.

환경 변수로 대상/자격을 바꿀 수 있다:
  - BACKEND_URL          기본값: 배포된 Railway 백엔드
  - SUPABASE_URL         미설정 시 backend/.env 에서 로드
  - SUPABASE_ANON_KEY    미설정 시 backend/.env 에서 로드

시드 계정(scripts/seed.py 기준):
  - admin@hospital.test    / Admin123!
  - doctor01@hospital.test / Doctor123!
  - patient01@hospital.test/ Patient123!
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

_BACKEND_DEFAULT = "https://backend-production-351c.up.railway.app"

ADMIN_CREDENTIALS = ("admin@hospital.test", "Admin123!")
DOCTOR_CREDENTIALS = ("doctor01@hospital.test", "Doctor123!")
PATIENT_CREDENTIALS = ("patient01@hospital.test", "Patient123!")


def _load_env_from_dotenv() -> dict[str, str]:
    """backend/.env 를 파싱해 dict로 반환 (의존성 없이)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


@pytest.fixture(scope="session")
def supabase_config() -> dict[str, str]:
    dotenv = _load_env_from_dotenv()
    url = os.environ.get("SUPABASE_URL") or dotenv.get("SUPABASE_URL")
    anon_key = os.environ.get("SUPABASE_ANON_KEY") or dotenv.get("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        pytest.skip("SUPABASE_URL / SUPABASE_ANON_KEY 미설정 — 통합 테스트 건너뜀")
    return {"url": url, "anon_key": anon_key}


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BACKEND_URL", _BACKEND_DEFAULT).rstrip("/")


def _login(supabase_config: dict[str, str], email: str, password: str) -> str:
    """Supabase 비밀번호 로그인 → access_token 반환."""
    resp = httpx.post(
        f"{supabase_config['url']}/auth/v1/token",
        params={"grant_type": "password"},
        headers={
            "apikey": supabase_config["anon_key"],
            "Content-Type": "application/json",
        },
        json={"email": email, "password": password},
        timeout=15.0,
    )
    if resp.status_code != 200:
        pytest.skip(
            f"로그인 실패({email}): {resp.status_code} {resp.text[:120]} "
            "— 시드 데이터/자격 증명을 확인하세요."
        )
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(supabase_config: dict[str, str]) -> str:
    return _login(supabase_config, *ADMIN_CREDENTIALS)


@pytest.fixture(scope="session")
def doctor_token(supabase_config: dict[str, str]) -> str:
    return _login(supabase_config, *DOCTOR_CREDENTIALS)


@pytest.fixture(scope="session")
def patient_token(supabase_config: dict[str, str]) -> str:
    return _login(supabase_config, *PATIENT_CREDENTIALS)


@pytest.fixture
def client(base_url: str):
    with httpx.Client(base_url=base_url, timeout=20.0) as c:
        yield c


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
