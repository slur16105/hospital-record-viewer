from __future__ import annotations
import logging
from pathlib import Path
from urllib.parse import urlparse
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

_env_file = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    cors_origins: str = "*"

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8"}

    def get_cors_origins(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        valid: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip()
            if not origin:
                continue
            parsed = urlparse(origin)
            # 브라우저 Origin은 scheme://host[:port] 형태로 정확히 일치해야 한다.
            # 경로·끝 슬래시·대문자·와일드카드 서브도메인은 조용한 CORS 실패의 원인 →
            # scheme+netloc만 소문자로 정규화하고, 매칭 불가한 형태는 경고 후 제외.
            if parsed.scheme in {"http", "https"} and parsed.netloc and "*" not in parsed.netloc:
                valid.append(f"{parsed.scheme}://{parsed.netloc}".lower())
            else:
                logger.warning("CORS_ORIGINS 무시 — 형식 오류: %r", origin)
        if not valid:
            logger.warning("유효한 CORS origin이 없습니다 — 교차출처 요청이 모두 차단됩니다")
        return valid


settings = Settings()
