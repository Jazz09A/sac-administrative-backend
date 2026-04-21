"""
Conexión de solo lectura hacia MySQL externo (fuente fiscales).
"""
from contextlib import asynccontextmanager
import logging
import ssl

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


def _conditional_log(msg: str, level: int = logging.INFO) -> None:
    """Log only in local environment."""
    if settings.is_local:
        logger.log(level, msg)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on", "strict", "require", "required"}


def _build_mysql_async_url(raw_url: str) -> tuple[URL, bool]:
    url = make_url(raw_url)
    original_query = dict(url.query)

    # Prisma often exports "mysql://..."; force async dialect for SQLAlchemy async engine.
    if not url.drivername.startswith("mysql+"):
        url = url.set(drivername="mysql+asyncmy")

    # Remove Prisma-specific params unsupported by asyncmy DBAPI.
    unsupported_query_keys = {
        # Prisma/MySQL URL params that asyncmy DBAPI doesn't accept directly.
        "sslaccept",
        "connection_limit",
        "pool_timeout",
        "socket_timeout",
        "connect_timeout",
    }
    cleaned_query = {k: v for k, v in url.query.items() if k not in unsupported_query_keys}
    dropped_keys = sorted(set(url.query.keys()) - set(cleaned_query.keys()))
    if dropped_keys:
        _conditional_log(f"Ignoring unsupported MySQL URL params for asyncmy: {dropped_keys}")

    require_ssl = settings.MYSQL_REQUIRE_SSL or any(
        _is_truthy(original_query.get(key)) for key in ("sslaccept", "sslmode", "ssl")
    )
    return url.set(query=cleaned_query), require_ssl


mysql_url, mysql_require_ssl = _build_mysql_async_url(settings.MYSQL_DATABASE_URL)
mysql_connect_args = {"ssl": ssl.create_default_context()} if mysql_require_ssl else {}

if mysql_require_ssl:
    _conditional_log("MySQL connection configured with TLS/SSL enabled.")

mysql_engine = create_async_engine(mysql_url, echo=False, connect_args=mysql_connect_args)
MySQLAsyncSessionLocal = async_sessionmaker(
    mysql_engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_mysql_session() -> AsyncSession:
    async with MySQLAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_mysql_db():
    async with get_mysql_session() as session:
        yield session
