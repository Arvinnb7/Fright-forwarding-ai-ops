"""API routers aggregated under a single router."""
from fastapi import APIRouter

from app.api import (
    auth,
    bookings,
    customers,
    exports,
    follow_ups,
    health,
    issues,
    mailbox,
    quotes,
    rates,
    reports,
    rfq,
    settings_api,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rfq.router, prefix="/rfqs", tags=["rfqs"])
api_router.include_router(rates.router, tags=["rates"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(follow_ups.router, prefix="/follow-ups", tags=["follow-ups"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(mailbox.router, prefix="/mailbox", tags=["mailbox"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
