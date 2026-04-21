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
    
    # Database (from .env)
    DATABASE_URL: str
    MYSQL_DATABASE_URL: str
    MYSQL_REQUIRE_SSL: bool = True
    FISCAL_SYNC_BATCH_SIZE: int = 500
    
    # Security
    SECRET_KEY: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    PROJECT_NAME: str = "Sistema Contribuyentes MVP"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Auth MVP (login operador)
    AUTH_PERSON_ID: str 
    AUTH_PASSWORD: str 
    ADMIN_EMAIL: str 

    # Feature flags MVP
    REQUIRE_AUTH: bool = False  # Future JWT

    # Cloud storage (Cloudflare R2 / S3 compatible)
    URL_BUCKET_S3: str = ""
    ACCESS_KEY_S3: str = ""
    TOKEN_VALUE_S3: str = ""
    SECRET_ACCESS_KEY_S3: str = ""
    BUCKET_NAME_S3: str = ""
    S3_REGION: str = "auto"
    # Base pública para construir URLs: custom domain o *.r2.dev
    # URL final = R2_PUBLIC_BASE_URL + "/" + object_key
    R2_PUBLIC_BASE_URL: str = ""

    # CORS (from .env - formato JSON: ["http://localhost:3000","https://miapp.com"])
    ALLOWED_ORIGINS: list[str]
@lru_cache()
def get_settings() -> Settings:
    return Settings()