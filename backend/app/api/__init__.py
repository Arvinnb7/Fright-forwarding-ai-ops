"""API routers aggregated under a single router."""
from fastapi import APIRouter, Depends

from app.core.deps import enforce_role_policy

from app.api import (
    audit,
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

# The role policy is attached to the router, not to individual routes: a
# permission you have to remember to add is one that will eventually be missed,
# and every endpoint added later would start out unguarded. See app/core/deps.py.
api_router = APIRouter(dependencies=[Depends(enforce_role_policy)])
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
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
