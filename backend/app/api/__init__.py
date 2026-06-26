"""API routers aggregated under a single router."""
from fastapi import APIRouter

from app.api import auth, health, rfq

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rfq.router, prefix="/rfqs", tags=["rfqs"])
