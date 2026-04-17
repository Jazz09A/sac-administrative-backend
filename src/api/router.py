from fastapi import APIRouter
from .v1.auth import router as auth_router
from .v1.contributors import router as contributors_router
from .v1.fiscals import router as fiscals_router
from .v1.visits import router as visits_router
from .v1.dashboard import router as dashboard_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(contributors_router, prefix="/contributors", tags=["contributors"])
api_router.include_router(fiscals_router, prefix="/fiscals", tags=["fiscals"])
api_router.include_router(visits_router, prefix="/visits", tags=["visits"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])