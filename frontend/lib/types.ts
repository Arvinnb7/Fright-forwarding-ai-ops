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
