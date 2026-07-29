"""ORM models. Importing this package registers every table on `Base.metadata`
and installs the multi-tenant query guards and the audit recorder."""
from app.core.audit import install_audit_trail
from app.core.tenancy import install_tenant_guards
from app.models.audit import AuditAction, AuditEvent
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.document import Document
from app.models.email_message import EmailMessage
from app.models.follow_up import FollowUp
from app.models.issue import Issue
from app.models.mailbox import MailboxConfig
from app.models.organization import Organization
from app.models.partner_rate import PartnerRate
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.models.user import User, UserRole

# Registered once, at import time: every ORM SELECT is filtered by the active
# organization and every INSERT is stamped with it (app/core/tenancy.py), and
# every change to a pricing, status or permission field is recorded
# (app/core/audit.py). Both are ORM-level so no code path can bypass them.
install_tenant_guards()
install_audit_trail()

__all__ = [
    "AuditAction",
    "AuditEvent",
    "Booking",
    "Customer",
    "Document",
    "EmailMessage",
    "FollowUp",
    "Issue",
    "MailboxConfig",
    "Organization",
    "PartnerRate",
    "Quote",
    "RFQ",
    "User",
    "UserRole",
]
