"""
Database session async Postgres.
Última mod: 2026-04-17 09:01 | Changes: AsyncSession engine.
"""
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

# Ensure SQLModel registry loads all mapped classes.
import src.models.asset  # noqa: F401
import src.models.contributor  # noqa: F401
import src.models.face_template  # noqa: F401
import src.models.fiscal  # noqa: F401
import src.models.photo  # noqa: F401
import src.models.user  # noqa: F401
import src.models.visit  # noqa: F401

from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.is_local)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Crea tables (dev only) y usuario admin inicial."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_visit_ticket_no ON visit (ticket_no)")
        )
    
    # Crear usuario admin inicial si no existe
    await _create_initial_admin()


async def _create_initial_admin():
    """Crea un usuario admin por defecto si no existe ninguno."""
    from sqlmodel import select

    from src.core.security import hash_password
    from src.models.user import User
    
    async with AsyncSessionLocal() as session:
        # Verificar si ya existe un admin
        result = await session.execute(select(User).where(User.role == "admin"))
        existing_admin = result.scalar_one_or_none()
        
        if not existing_admin:
            # Crear usuario admin por defecto
            admin_user = User(
                person_id=settings.AUTH_PERSON_ID,
                full_name="Administrador del Sistema",
                email=settings.ADMIN_EMAIL,
                is_active=True,
                role="admin",
                hashed_password=hash_password(settings.AUTH_PASSWORD),
            )
            session.add(admin_user)
            await session.commit()
            # print(f"✅ Usuario admin creado: person_id={settings.AUTH_PERSON_ID}, password={settings.AUTH_PASSWORD}")

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