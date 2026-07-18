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
}
