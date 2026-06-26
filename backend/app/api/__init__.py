"""API routers aggregated under a single router."""
from fastapi import APIRouter

from app.api import auth, follow_ups, health, quotes, rates, reports, rfq

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rfq.router, prefix="/rfqs", tags=["rfqs"])
api_router.include_router(rates.router, tags=["rates"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(follow_ups.router, prefix="/follow-ups", tags=["follow-ups"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
