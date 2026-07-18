import type { JobSpec, ParsedDoc } from "./types";

export const MOCK_SESSION = {
  user: { id: "mock-user", email: "demo@negotiator.pk" },
  access_token: "mock_token",
} as const;

export const MOCK_SPEC: JobSpec = {
  vertical: "commercial_shop_rental_pk",
  currency: "PKR",
  area_sqft: 400,
  location: "Gulberg III, Lahore",
  floor: "ground",
  business_type: "electronics retail",
  frontage_ft: 14,
  lease_years: 3,
  parking: true,
  move_in: "2026-08-01",
  current_rent: 85000,
  budget_monthly_rent: 95000,
  _source: {
    area_sqft: "doc",
    location: "voice",
    floor: "voice",
    business_type: "voice",
    frontage_ft: "doc",
    lease_years: "voice",
    parking: "voice",
    move_in: "voice",
    current_rent: "doc",
    budget_monthly_rent: "voice",
  },
};

export const MOCK_PARSE_RENT_AGREEMENT: ParsedDoc = {
  kind: "rent_agreement",
  partial_spec: { area_sqft: 400, frontage_ft: 14, current_rent: 85000 },
  raw_text_preview: "This Rent Agreement is made on the 1st day of...",
};

export const MOCK_PARSE_REQUIREMENTS: ParsedDoc = {
  kind: "requirements",
  partial_spec: {
    location: "Gulberg III, Lahore",
    business_type: "electronics retail",
    lease_years: 3,
  },
  raw_text_preview: "We are looking for a ground floor shop suitable for...",
};
