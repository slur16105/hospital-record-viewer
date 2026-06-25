from pathlib import Path
from pydantic_settings import BaseSettings

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
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
