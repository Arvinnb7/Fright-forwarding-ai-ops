"""ORM models. Importing this package registers every table on `Base.metadata`
and installs the multi-tenant query guards."""
from app.core.tenancy import install_tenant_guards
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.document import Document
from app.models.follow_up import FollowUp
from app.models.issue import Issue
from app.models.organization import Organization
from app.models.partner_rate import PartnerRate
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.models.user import User, UserRole

# Registered once, at import time: every ORM SELECT is filtered by the active
# organization and every INSERT is stamped with it. See app/core/tenancy.py.
install_tenant_guards()

__all__ = [
    "Booking",
    "Customer",
    "Document",
    "FollowUp",
    "Issue",
    "Organization",
    "PartnerRate",
    "Quote",
    "RFQ",
    "User",
    "UserRole",
]
