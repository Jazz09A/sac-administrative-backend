"""
Configuración app-wide con Pydantic Settings.
Última mod: 2026-04-17 09:01 | Changes: DATABASE_URL, SECRET_KEY, Postgres async.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:Seniat2026$@localhost:5432/sac-administrative-development"
    MYSQL_DATABASE_URL: str = "mysql+asyncmy://nEyKV8sWBL1LVH1.root:CaxbMMZ10VoSgZaz@gateway01.eu-central-1.prod.aws.tidbcloud.com:4000/development_sac?sslaccept=strict&connection_limit=100&pool_timeout=20"
    MYSQL_REQUIRE_SSL: bool = True
    FISCAL_SYNC_BATCH_SIZE: int = 500
    
    # Security
    SECRET_KEY: str = "change-me-super-secret-key-long-random"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    PROJECT_NAME: str = "Sistema Contribuyentes MVP"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Auth MVP (login operador)
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = "admin"

    # Feature flags MVP
    REQUIRE_AUTH: bool = False  # Future JWT

@lru_cache()
def get_settings() -> Settings:
    return Settings()