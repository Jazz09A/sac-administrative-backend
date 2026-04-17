"""
FastAPI app principal. Modular routers.
Última mod: 2026-04-17 09:03 | Changes: Init app, CORS, DB deps, v1 routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from src.core.config import get_settings
from src.core.database import init_db
from src.api.router import api_router

logger = logging.getLogger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    # DB init on startup (dev)
    try:
        await init_db()
    except Exception as exc:
        # Allow API startup even if DB is temporarily unavailable.
        logger.warning("Database init skipped during startup: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS (frontend React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite/React dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.VERSION}

# API v1
app.include_router(api_router, prefix=settings.API_V1_STR, tags=["v1"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)