// Shared types mirroring the backend Pydantic schemas.

export interface RFQ {
  id: number;
  reference: string | null;
  customer_id: number | null;
  origin: string | null;
  destination: string | null;
  transport_mode: string | null;
  shipment_type: string | null;
  container_type: string | null;
  commodity: string | null;
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
