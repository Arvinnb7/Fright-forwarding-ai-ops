"""ORM models. Importing this package registers every table on `Base.metadata`."""
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.document import Document
from app.models.follow_up import FollowUp
from app.models.issue import Issue
from app.models.partner_rate import PartnerRate
from app.models.quote import Quote
from app.models.rfq import RFQ
from app.models.user import User

__all__ = [
    "Booking",
    "Customer",
    "Document",
    "FollowUp",
    "Issue",
    "PartnerRate",
    "Quote",
    "RFQ",
    "User",
]
