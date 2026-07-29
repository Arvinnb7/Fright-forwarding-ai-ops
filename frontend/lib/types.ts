// Shared types mirroring the backend Pydantic schemas.

export interface RFQ {
  id: number;
  reference: string | null;
  customer_id: number | null;
  raw_message: string | null;
  origin: string | null;
  destination: string | null;
  pickup_address: string | null;
  delivery_address: string | null;
  transport_mode: string | null;
  shipment_type: string | null;
  container_type: string | null;
  commodity: string | null;
  hs_code: string | null;
  gross_weight: string | null;
  cbm: string | null;
  dimensions: string | null;
  package_count: string | null;
  incoterm: string | null;
  missing_fields: string[];
  requested_charges: string[];
  recommended_next_action: string | null;
  urgency: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface RFQExtraction {
  origin: string | null;
  destination: string | null;
  transport_mode: string | null;
  shipment_type: string | null;
  container_type: string | null;
  commodity: string | null;
  gross_weight: string | null;
  incoterm: string | null;
  cargo_ready_date_text: string | null;
  requested_charges: string[];
  missing_fields: string[];
  urgency: string;
  recommended_next_action: string | null;
  [key: string]: unknown;
}

export interface PartnerRate {
  id: number;
  rfq_id: number;
  partner_name: string;
  partner_type: string | null;
  cost_amount: number | null;
  currency: string;
  included_charges: string | null;
  excluded_charges: string | null;
  transit_time: string | null;
  validity_date: string | null;
  free_time: string | null;
  notes: string | null;
  risk_notes: string | null;
  reliability_score: number | null;
  created_at: string;
}

export interface RateOption {
  rate_id: number;
  partner_name: string;
  summary: string;
  pros: string[];
  cons: string[];
  risk_notes: string | null;
}

export interface RateAnalysis {
  cheapest_rate_id: number | null;
  fastest_rate_id: number | null;
  best_margin_rate_id: number | null;
  lowest_risk_rate_id: number | null;
  recommended_rate_id: number | null;
  recommendation_reason: string | null;
  tradeoffs: string | null;
  options: RateOption[];
}

export interface QuotePricingReview {
  quote_id: number;
  cost_amount: number | null;
  selling_price: number | null;
  gross_margin: number | null;
  gross_margin_percentage: number | null;
  currency: string;
  warnings: string[];
  draft_text: string;
}

export interface Quote {
  id: number;
  quote_number: string | null;
  rfq_id: number | null;
  customer_id: number | null;
  selected_rate_id: number | null;
  cost_amount: number | null;
  selling_price: number | null;
  currency: string;
  gross_margin: number | null;
  gross_margin_percentage: number | null;
  validity_date: string | null;
  quote_text: string | null;
  status: string;
  sent_at: string | null;
  next_follow_up_date: string | null;
  lost_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface FollowUp {
  id: number;
  quote_id: number;
  customer_id: number | null;
  due_date: string | null;
  status: string;
  draft_message: string | null;
  sent_manually: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardMetrics {
  date: string;
  rfqs_received: number;
  quotes_sent: number;
  pending_rates: number;
  confirmed_bookings: number;
  follow_ups_due: number;
  lost_today: number;
  won_today: number;
  estimated_pipeline: number;
  estimated_margin: number;
  high_value_opportunities: {
    quote_number: string | null;
    selling_price: number | null;
    currency: string;
    status: string;
  }[];
}

export const PARTNER_TYPES = [
  "Shipping line",
  "Airline",
  "Overseas agent",
  "Destination agent",
  "Trucking company",
  "Customs broker",
  "Warehouse provider",
  "Project cargo / heavy lift",
  "Port handling agent",
];

export const RFQ_STATUSES = [
  "New",
  "Incomplete",
  "Ready for pricing",
  "Waiting for customer info",
  "Waiting for partner rates",
  "Quoted",
  "Follow-up due",
  "Won",
  "Lost",
  "Cancelled",
];

export interface Customer {
  id: number;
  company_name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  country: string | null;
  city: string | null;
  industry: string | null;
  notes: string | null;
  next_follow_up_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerStats {
  rfq_count: number;
  quote_count: number;
  won_count: number;
  lost_count: number;
  average_margin_percentage: number | null;
  typical_routes: string[];
}

export interface Booking {
  id: number;
  job_number: string | null;
  quote_id: number | null;
  customer_id: number | null;
  shipper: string | null;
  consignee: string | null;
  notify_party: string | null;
  origin: string | null;
  destination: string | null;
  cargo_details: string | null;
  agreed_price: number | null;
  estimated_cost: number | null;
  estimated_margin: number | null;
  currency: string;
  assigned_to: string | null;
  status: string;
  etd: string | null;
  eta: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShipmentDocument {
  id: number;
  booking_id: number;
  document_type: string;
  status: string;
  notes: string | null;
  file_name: string | null;
  file_size_bytes: number | null;
  content_type: string | null;
  has_file: boolean;
  created_at: string;
  updated_at: string;
}

export interface MailboxConfig {
  id: number;
  host: string;
  port: number;
  use_ssl: boolean;
  username: string;
  folder: string;
  is_enabled: boolean;
  last_seen_uid: number | null;
  last_polled_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface EmailAttachment {
  filename: string;
  content_type: string;
  size_bytes: number;
  path?: string;
  error?: string;
}

export interface EmailMessage {
  id: number;
  message_id: string;
  thread_key: string | null;
  from_address: string | null;
  from_name: string | null;
  subject: string | null;
  body: string | null;
  received_at: string | null;
  classification: string;
  classification_confidence: number | null;
  classification_reason: string | null;
  status: string;
  error: string | null;
  rfq_id: number | null;
  quote_id: number | null;
  attachments: EmailAttachment[];
  created_at: string;
}

export interface IngestRunResult {
  fetched: number;
  skipped_duplicates: number;
  rfqs_created: number;
  rate_replies_linked: number;
  customer_replies_linked: number;
  ignored: number;
  failed: number;
}

export const EMAIL_CLASSIFICATIONS = [
  "New RFQ",
  "Partner rate reply",
  "Customer reply",
  "Not relevant",
  "Unclassified",
];

export interface Issue {
  id: number;
  booking_id: number | null;
  issue_type: string;
  severity: string;
  description: string | null;
  responsible_party: string | null;
  next_action: string | null;
  due_date: string | null;
  status: string;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export const BOOKING_STATUSES = [
  "Booking confirmed",
  "Awaiting documents",
  "Pickup scheduled",
  "Cargo received",
  "Booked with carrier/agent",
  "In transit",
  "Arrived at destination",
  "Under customs clearance",
  "Out for delivery",
  "Delivered",
  "Closed",
];

export const DOCUMENT_STATUSES = [
  "Required",
  "Received",
  "Missing",
  "Expired",
  "Needs correction",
];

export const ISSUE_TYPES = [
  "Missing document",
  "Wrong document",
  "Rate changed",
  "Carrier delay",
  "Vessel rollover",
  "Customs hold",
  "Extra charges",
  "Truck delay",
  "Customer complaint",
  "Agent not responding",
  "Payment issue",
  "Delivery issue",
];

export const QUOTE_STATUSES = [
  "Draft",
  "Pending approval",
  "Approved",
  "Sent",
  "Follow-up due",
  "Negotiating",
  "Won",
  "Lost",
  "Expired",
];
