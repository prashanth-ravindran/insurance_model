export type Role = 'agent' | 'underwriter' | 'manager';
export type Channel = 'manual' | 'api';
export type ConfidenceLevel = 'high' | 'low';
export type Status =
  | 'draft'
  | 'submitted'
  | 'enriched'
  | 'stp_quoted'
  | 'requires_review'
  | 'declined'
  | 'underwriter_approved'
  | 'underwriter_declined'
  | 'quoted'
  | 'bound';

export interface Applicant {
  name: string;
  applicant_type: 'individual' | 'company';
  national_id_or_cr: string;
  email?: string;
  phone?: string;
}

export interface PolicyPayload {
  [key: string]: string | number | undefined;
  lob: string;
  region: string;
  counterparty_rating: string;
  exposure_value_sar: number;
  limit_sar: number;
  deductible_sar: number;
  term_months: number;
  prior_claims_3y: number;
  risk_control_score: number;
  reinsurance_ceded_pct: number;
  event_accumulation_score: number;
}

export interface ApplicationCreate {
  channel: Channel;
  submitted_by: string;
  role: Role;
  applicant: Applicant;
  policy: PolicyPayload;
  requested_coverages: Record<string, unknown>;
}

export interface FieldConfidence {
  confidence: ConfidenceLevel;
  evidence?: string | null;
  rationale?: string | null;
}

export type UnstructuredStatus =
  | 'uploaded'
  | 'extracting'
  | 'needs_review'
  | 'approved'
  | 'rejected'
  | 'application_created'
  | 'failed';

export interface UnstructuredRecord {
  id: string;
  parent_id: string | null;
  batch_index: number;
  status: UnstructuredStatus;
  original_filename: string;
  content_type: string | null;
  file_extension: string;
  storage_path: string;
  raw_text: string;
  raw_preview: { kind?: string; text?: string; [key: string]: unknown };
  extraction: { application?: ApplicationCreate; [key: string]: unknown };
  field_confidence: Record<string, FieldConfidence>;
  source_evidence: Record<string, string | null>;
  missing_fields: string[];
  warnings: string[];
  reviewer_edits: Record<string, unknown> | null;
  review_notes: string | null;
  reviewer: string | null;
  application_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UnstructuredReviewResponse {
  record: UnstructuredRecord;
  application: UnderwritingCase | null;
}

export interface EnrichmentFlag {
  code: string;
  label: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
}

export interface EnrichmentResult {
  provider: string;
  status: string;
  confidence: number;
  data: Record<string, unknown>;
  flags: EnrichmentFlag[];
  requested_at: string;
  completed_at: string;
}

export interface DecisionResult {
  decision_bucket: 'stp' | 'requires_review' | 'declined';
  engine_decision: string;
  reasons: string[];
  recommended_actions: string[];
  rule_evaluations: Array<Record<string, unknown>>;
  enrichment_flags: EnrichmentFlag[];
}

export interface PricingAdjustment {
  code: string;
  label: string;
  kind: 'discount' | 'surcharge' | 'schedule';
  pct: number;
  amount_sar: number;
  reason: string;
}

export interface RatingResult {
  base_premium_sar: number | null;
  adjusted_premium_sar: number | null;
  expected_loss_sar: number;
  risk_score: number;
  scr_impact_sar: number;
  premium_breakdown: Record<string, number>;
  adjustments: PricingAdjustment[];
  pricing_reconciliation: Array<Record<string, unknown>>;
  model_basis: string;
}

export interface QuoteRecord {
  id: string;
  quote_id: string;
  quote_number: string;
  application_id: string;
  premium_sar: number;
  decision_bucket: string;
  deductible_sar: number;
  sublimits: Record<string, number>;
  exclusions: string[];
  expires_at: string;
  generated_by: string;
  created_at: string;
  pdf_path: string;
}

export interface BoundPolicy {
  id: string;
  policy_number: string;
  quote_id: string;
  application_id: string;
  premium_sar: number;
  bound_by: string;
  bound_at: string;
}

export interface AuditEvent {
  id: number;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface UnderwritingCase {
  id: string;
  status: Status;
  channel: Channel;
  submitted_by: string;
  assigned_to: string | null;
  applicant: Applicant;
  policy: PolicyPayload;
  requested_coverages: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  enrichments: EnrichmentResult[];
  decisions: DecisionResult[];
  ratings: RatingResult[];
  reviews: Array<Record<string, unknown>>;
  quotes: QuoteRecord[];
  bound_policies: BoundPolicy[];
  audit_events: AuditEvent[];
  latest_decision: DecisionResult | null;
  latest_rating: RatingResult | null;
  latest_review: Record<string, unknown> | null;
  latest_quote: QuoteRecord | null;
}

export interface ConfigPayload {
  lobs: string[];
  regions: Record<string, Record<string, number>>;
  lob_config: Record<string, Record<string, number>>;
  counterparty_ratings: string[];
  decision_thresholds: Record<string, number>;
  scenarios: Record<string, Record<string, string | number>>;
  roles: Role[];
  channels: Channel[];
}
