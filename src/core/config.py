"""
Configuración app-wide con Pydantic Settings.
Última mod: 2026-04-17 09:01 | Changes: DATABASE_URL, SECRET_KEY, Postgres async.
"""
from functools import lru_cache
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # Environment
    ENVIRONMENT: str = "production"

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT.lower() in ("local", "development", "dev")

    # Database (from .env)
    DATABASE_URL: str
    DB_PRODUCTION_URL: str | None = None
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
    STORAGE_PROVIDER: str = "s3"  # "s3" or "supabase"
    URL_BUCKET_S3: str = ""
    ACCESS_KEY_S3: str = ""
    TOKEN_VALUE_S3: str = ""
    SECRET_ACCESS_KEY_S3: str = ""
    BUCKET_NAME_S3: str = ""
    S3_REGION: str = "auto"
    # Base pública para construir URLs: custom domain o *.r2.dev
    # URL final = R2_PUBLIC_BASE_URL + "/" + object_key
    R2_PUBLIC_BASE_URL: str = ""

    # Supabase storage
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    BUCKET_NAME_SUPABASE: str = ""

    # CORS (from .env - formato JSON o separado por comas)
    ALLOWED_ORIGINS: list[str] = []

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        import logging
        logger = logging.getLogger(__name__)
        
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
            logger.info(f"[CORS-PARSE] Detectado formato CSV. Orígenes: {origins}")
            return origins
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                origins = json.loads(v)
                logger.info(f"[CORS-PARSE] Detectado formato JSON. Orígenes: {origins}")
                return origins
            except Exception as e:
                logger.error(f"[CORS-PARSE] Error parseando JSON de ALLOWED_ORIGINS: {e}")
                return []
        return v

    @model_validator(mode="after")
    def validate_storage_settings(self) -> "Settings":
        provider = self.STORAGE_PROVIDER.strip().lower()

        if provider not in {"s3", "supabase"}:
            raise ValueError("STORAGE_PROVIDER debe ser 's3' o 'supabase'")

        if provider == "supabase":
            supabase_url = self.SUPABASE_URL.strip().rstrip("/")
            if not supabase_url:
                raise ValueError("SUPABASE_URL es obligatorio para STORAGE_PROVIDER=supabase")
            if ".storage.supabase.co" in supabase_url or "/storage/v1" in supabase_url:
                raise ValueError(
                    "SUPABASE_URL invalido: use la URL del proyecto "
                    "(https://<project-ref>.supabase.co), no el endpoint S3/Storage."
                )

            if not self.SUPABASE_KEY.strip():
                raise ValueError("SUPABASE_KEY es obligatorio para STORAGE_PROVIDER=supabase")
            if not self.BUCKET_NAME_SUPABASE.strip():
                raise ValueError("BUCKET_NAME_SUPABASE es obligatorio para STORAGE_PROVIDER=supabase")

        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()