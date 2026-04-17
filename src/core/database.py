"""
Database session async Postgres.
Última mod: 2026-04-17 09:01 | Changes: AsyncSession engine.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel
from contextlib import asynccontextmanager

from .config import get_settings

# Ensure SQLModel registry loads all mapped classes.
import src.models.contributor  # noqa: F401
import src.models.fiscal  # noqa: F401
import src.models.photo  # noqa: F401
import src.models.user  # noqa: F401
import src.models.visit  # noqa: F401

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Crea tables (dev only)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@asynccontextmanager
async def get_session() -> AsyncSession:
    """Session manager para Depends."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_db():
    async with get_session() as session:
        yield session