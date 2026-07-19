// Mirrors backend/config/vertical.json spec_schema. If K1 changes it, update here + mocks.ts.
export type Floor = "ground" | "first" | "basement";

export type FieldSource = "voice" | "doc" | "manual" | "unset";

export interface JobSpec {
  id?: string; // supabase spec id, present after Confirm
  vertical: "commercial_shop_rental_pk";
  currency: "PKR";
  area_sqft: number | null;
  location: string;
  floor: Floor | null;
  business_type: string;
  frontage_ft: number | null;
  lease_years: number | null;
  parking: boolean | null;
  move_in: string | null; // ISO date "2026-08-01"
  current_rent: number | null;
  budget_monthly_rent: number | null;
  _source: Partial<
    Record<
      keyof Omit<JobSpec, "_source" | "id" | "vertical" | "currency">,
      FieldSource
    >
  >;
}

export const REQUIRED_SPEC_FIELDS: (keyof JobSpec)[] = [
  "area_sqft",
  "location",
  "floor",
  "business_type",
  "lease_years",
  "move_in",
  "budget_monthly_rent",
];

// Render order in SpecConfirmForm — matches the estimator voice flow.
export const SPEC_FIELD_ORDER: (keyof JobSpec)[] = [
  "location",
  "area_sqft",
  "frontage_ft",
  "floor",
  "business_type",
  "lease_years",
  "parking",
  "move_in",
  "current_rent",
  "budget_monthly_rent",
];

export type SpecFieldType = "number" | "string" | "enum" | "bool" | "date";

export interface SpecFieldMeta {
  label: string;
  type: SpecFieldType;
  values?: readonly string[];
}

// Mirrors vertical.json spec_schema field metadata for form rendering.
export const SPEC_FIELD_META: Record<
  Exclude<keyof JobSpec, "_source" | "id" | "vertical" | "currency">,
  SpecFieldMeta
> = {
  area_sqft: { label: "Area (sqft)", type: "number" },
  location: { label: "Location", type: "string" },
  floor: { label: "Floor", type: "enum", values: ["ground", "first", "basement"] },
  business_type: { label: "Business type", type: "string" },
  frontage_ft: { label: "Frontage (ft)", type: "number" },
  lease_years: { label: "Lease (years)", type: "number" },
  parking: { label: "Parking", type: "bool" },
  move_in: { label: "Move-in date", type: "date" },
  current_rent: { label: "Current rent (PKR/mo)", type: "number" },
  budget_monthly_rent: { label: "Budget monthly rent (PKR)", type: "number" },
};

export interface ParsedDoc {
  kind: "rent_agreement" | "requirements";
  partial_spec: Partial<JobSpec>;
  raw_text_preview: string;
}

export interface IntakeSubmitResponse {
  spec_id: string;
  dealers_seeded: number;
  dealers_discovered?: number;
}

// ── K9 Call Center — mirrors backend calls/quotes/dealers shapes ──

export type Persona = "stonewaller" | "lowballer" | "upseller" | "firm" | "human";

export const PERSONAS: readonly Persona[] = [
  "stonewaller",
  "lowballer",
  "upseller",
  "firm",
  "human",
];

// undefined/missing = active; only "declined" ever blocks calling.
export type DealerStatus = "active" | "declined";

export interface Dealer {
  id: string;
  spec_id: string;
  name: string;
  persona: Persona;
  phone_label?: string | null;
  source?: string | null;
  status?: DealerStatus;
}

export interface TranscriptLine {
  line: number;
  speaker: "negotiator" | "dealer";
  text: string;
}

// Backend statuses; UI adds idle/calling/live on top (see UiCallState).
export type CallStatus = "running" | "completed" | "failed";
export type CallOutcome =
  | "quote"
  | "final_quote"
  | "vague_quote"
  | "declined"
  | "callback"
  | "failed";

export interface CallRow {
  id: string;
  spec_id: string;
  dealer_id: string;
  round: number;
  status: CallStatus;
  started_at?: string | null;
  ended_at?: string | null;
  recording_url?: string | null;
  transcript_json?: TranscriptLine[] | null;
  outcome?: CallOutcome | null;
  callback_at?: string | null;
  callback_note?: string | null;
}

// Shared label copy for CallOutcome — reused by CallStatusPanel and DealerCard
// so the two never drift apart.
export const OUTCOME_COPY: Record<
  CallOutcome,
  { label: string; tone: "success" | "error" | "neutral" }
> = {
  quote: { label: "Quote logged", tone: "success" },
  final_quote: { label: "Final quote — dealer confirmed no further room", tone: "success" },
  vague_quote: { label: "Verbal numbers only — no written quote", tone: "neutral" },
  declined: { label: "Dealer declined — unit not available", tone: "error" },
  callback: { label: "Dealer asked for a callback", tone: "neutral" },
  failed: { label: "Call failed before completing", tone: "error" },
};

export interface Quote {
  id?: string;
  call_id: string;
  dealer_id: string;
  monthly_rent: number;
  advance_months?: number | null;
  commission?: number | null;
  maintenance?: number | null;
  annual_increment_pct?: number | null;
  other_fees?: Record<string, number> | null;
  total_first_year: number;
  binding?: boolean;
  notes?: string | null;
  flagged?: boolean;
  flag_reason?: string | null;
  // Identifies which of a dealer's several matching shops this quote is for.
  // null/absent = the dealer's single/only property.
  property_ref?: string | null;
}

// ── Past-calls dashboard (/) — reuses JobSpec/Dealer/CallRow, no forking ──

export interface SpecListItem {
  id: string;
  created_at?: string | null;
  confirmed: boolean;
  spec: Partial<JobSpec>; // from spec_json
}

export type ProgressState =
  | { kind: "intake" }
  | { kind: "ready_to_call" }
  | { kind: "calling"; done: number; total: number }
  | { kind: "report_ready" };

export interface SpecListEntry {
  item: SpecListItem;
  progress: ProgressState;
}

// ── K10 Report — reuses Quote/CallOutcome/Persona as-is, no forking ──

export interface ReportRow {
  dealer_id: string;
  dealer_name: string;
  persona: Persona;
  // Which of the dealer's properties this row is for; null for a single-property
  // dealer. Combined with dealer_id, distinguishes several rows from one dealer.
  property_ref?: string | null;
  // Stable per-row key (`${dealer_id}:${property_ref ?? ""}`) — use as the React
  // key and to match recommended_row_id; a dealer can produce several rows.
  row_id: string;
  rank: number | null; // null only for declined/no-quote dealers — never omitted, just unranked
  quote: Quote | null;
  round: number;
  outcome: CallOutcome;
  // Stable 1-based citation number. Real mode: assigned by the backend report
  // generator from the spec's calls ordered by started_at. Mock: MOCK_DEALERS index+1.
  call_number: number;
  citation_line: number; // line in that call's transcript this row's claim is backed by
  recording_url?: string | null;
}

export interface Report {
  spec_id: string;
  rows: ReportRow[];
  // null when no dealer produced a quote — recommendation_text explains why.
  recommended_dealer_id: string | null;
  // Identifies the specific recommended row (dealer+property) — use this to
  // highlight the right row when a dealer has more than one.
  recommended_row_id: string | null;
  recommendation_text: string;
  // no separate citation field — RecommendationBlock reads call_number/citation_line
  // off the recommended row itself, so the table and the recommendation can't drift apart.
}

export interface CallStartResponse {
  call_id: string;
  status?: CallStatus;
  // roleplay mode only:
  negotiator_agent_id?: string;
  dynamic_variables?: Record<string, unknown>;
}

// Client-side call lifecycle: idle → calling (POST in flight) → live
// (backend "running") → done ("completed") | failed.
export type UiCallState = "idle" | "calling" | "live" | "done" | "failed";
