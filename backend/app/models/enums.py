"""Domain enums shared across models and schemas.

Plain str-Enums so they serialize cleanly to JSON and can be stored as DB
string enums via SQLAlchemy's native Enum type.
"""
from __future__ import annotations

from enum import Enum


class TransportMode(str, Enum):
    SEA = "Sea"
    AIR = "Air"
    ROAD = "Road"
    RAIL = "Rail"
    MULTIMODAL = "Multimodal"


class ShipmentType(str, Enum):
    FCL = "FCL"
    LCL = "LCL"
    BREAKBULK = "Breakbulk"
    PROJECT_CARGO = "Project Cargo"
    TRUCKING = "Trucking"
    AIR_CARGO = "Air Cargo"


class Urgency(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    CRITICAL = "Critical"


class RFQStatus(str, Enum):
    NEW = "New"
    INCOMPLETE = "Incomplete"
    READY_FOR_PRICING = "Ready for pricing"
    WAITING_FOR_CUSTOMER = "Waiting for customer info"
    WAITING_FOR_RATES = "Waiting for partner rates"
    QUOTED = "Quoted"
    FOLLOW_UP_DUE = "Follow-up due"
    WON = "Won"
    LOST = "Lost"
    CANCELLED = "Cancelled"


class PartnerType(str, Enum):
    SHIPPING_LINE = "Shipping line"
    AIRLINE = "Airline"
    OVERSEAS_AGENT = "Overseas agent"
    DESTINATION_AGENT = "Destination agent"
    TRUCKING = "Trucking company"
    CUSTOMS_BROKER = "Customs broker"
    WAREHOUSE = "Warehouse provider"
    PROJECT_CARGO = "Project cargo / heavy lift"
    PORT_HANDLING = "Port handling agent"


class QuoteStatus(str, Enum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending approval"
    APPROVED = "Approved"
    SENT = "Sent"
    FOLLOW_UP_DUE = "Follow-up due"
    NEGOTIATING = "Negotiating"
    WON = "Won"
    LOST = "Lost"
    EXPIRED = "Expired"


class BookingStatus(str, Enum):
    BOOKING_CONFIRMED = "Booking confirmed"
    AWAITING_DOCUMENTS = "Awaiting documents"
    PICKUP_SCHEDULED = "Pickup scheduled"
    CARGO_RECEIVED = "Cargo received"
    BOOKED_WITH_CARRIER = "Booked with carrier/agent"
    IN_TRANSIT = "In transit"
    ARRIVED_DESTINATION = "Arrived at destination"
    UNDER_CUSTOMS = "Under customs clearance"
    OUT_FOR_DELIVERY = "Out for delivery"
    DELIVERED = "Delivered"
    CLOSED = "Closed"


class DocumentStatus(str, Enum):
    REQUIRED = "Required"
    RECEIVED = "Received"
    MISSING = "Missing"
    EXPIRED = "Expired"
    NEEDS_CORRECTION = "Needs correction"


class IssueSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class IssueStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class FollowUpStatus(str, Enum):
    PENDING = "Pending"
    DUE = "Due"
    SENT = "Sent"
    REPLIED = "Replied"
    COLD = "Cold"
    CLOSED = "Closed"
