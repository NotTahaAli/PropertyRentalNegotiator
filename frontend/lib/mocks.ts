import type {
  CallOutcome,
  Dealer,
  JobSpec,
  ParsedDoc,
  Quote,
  TranscriptLine,
} from "./types";

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

// ── K9 Call Center mocks ──

export const MOCK_DEALERS: Dealer[] = [
  { id: "dealer_stonewaller", spec_id: "spec_mock_001", name: "Stonewaller Dealer", persona: "stonewaller", phone_label: "Dealer (stonewaller)", source: "seed" },
  { id: "dealer_lowballer", spec_id: "spec_mock_001", name: "Lowballer Dealer", persona: "lowballer", phone_label: "Dealer (lowballer)", source: "seed" },
  { id: "dealer_upseller", spec_id: "spec_mock_001", name: "Upseller Dealer", persona: "upseller", phone_label: "Dealer (upseller)", source: "seed" },
  { id: "dealer_firm", spec_id: "spec_mock_001", name: "Firm Dealer", persona: "firm", phone_label: "Dealer (firm)", source: "seed" },
  // K7 dealer discovery — real dealers found via Tavily land with persona "human"
  { id: "dealer_tavily_alpha", spec_id: "spec_mock_001", name: "Alpha Estate & Builders", persona: "human", phone_label: "https://alpha-estate.pk", source: "tavily" },
];

export const PERSONA_HINTS: Record<Dealer["persona"], string> = {
  stonewaller: "Cagey — resists itemised breakdowns",
  lowballer: "Suspiciously cheap, vague on details",
  upseller: "Piles on fees beyond base rent",
  firm: "Transparent, market-rate, barely moves",
  human: "Real dealer — role-play or assign a persona",
};

function t(line: number, speaker: TranscriptLine["speaker"], text: string): TranscriptLine {
  return { line, speaker, text };
}

// Stonewaller ends declined — no quote logged. Demo shows non-quote outcomes honestly.
export const MOCK_TRANSCRIPTS: Record<Dealer["persona"], TranscriptLine[]> = {
  stonewaller: [
    t(1, "negotiator", "Assalam-o-Alaikum, I'm calling on behalf of a client looking to rent a commercial shop in Gulberg, around 400 square feet, ground floor."),
    t(2, "dealer", "Yes, we have shops. Good area, very good area."),
    t(3, "negotiator", "Great. Could you give me the monthly rent for something matching that?"),
    t(4, "dealer", "Rent is fine, don't worry. Around one and a half lakh, all included."),
    t(5, "negotiator", "When you say all included — what is the advance, commission, and monthly maintenance separately?"),
    t(6, "dealer", "These things we can discuss when you visit. Lease is flexible, area is prime."),
    t(7, "negotiator", "I understand, but my client needs the itemised numbers before visiting. What advance do you require?"),
    t(8, "dealer", "Advance is standard. Everyone pays standard."),
    t(9, "negotiator", "Could you commit any of this in writing? A draft agreement or written quote?"),
    t(10, "dealer", "Actually that shop, let me check... it may already be committed to another party. Call some other time."),
    t(11, "negotiator", "So the unit is not available? Should I note this as declined?"),
    t(12, "dealer", "Yes, already rented. Khuda hafiz."),
  ],
  lowballer: [
    t(1, "negotiator", "Assalam-o-Alaikum, I'm calling for a client seeking a 400 square foot ground-floor shop in Gulberg."),
    t(2, "dealer", "Hello ji! Perfect timing, I have exactly this. Only 65,000 monthly."),
    t(3, "negotiator", "65,000 for Gulberg ground floor is well below the usual range. What condition is the shop in?"),
    t(4, "dealer", "Great deal, that's just what the owner wants. Quick decision needed."),
    t(5, "negotiator", "What advance and commission are you asking?"),
    t(6, "dealer", "Two months advance, 130,000. Commission only half month, 32,500."),
    t(7, "negotiator", "And monthly maintenance charges?"),
    t(8, "dealer", "Nothing much, 3,000 only."),
    t(9, "negotiator", "Annual increment percentage?"),
    t(10, "dealer", "Five percent, standard."),
    t(11, "negotiator", "Can you provide a written agreement with these numbers?"),
    t(12, "dealer", "Written... owner handles that later. First give token money, then paperwork."),
    t(13, "negotiator", "I'll log these figures and my client will decide. Thank you."),
  ],
  upseller: [
    t(1, "negotiator", "Assalam-o-Alaikum, I'm enquiring about a 400 square foot ground-floor shop in Gulberg for a client."),
    t(2, "dealer", "Good day! Excellent property available. Base rent 95,000 monthly."),
    t(3, "negotiator", "What advance do you require on that?"),
    t(4, "dealer", "Six months advance, 570,000. Prime location, this is normal."),
    t(5, "negotiator", "Six months is above the usual two to three. What about commission?"),
    t(6, "dealer", "One and a half month commission, 142,500. Standard practice."),
    t(7, "negotiator", "Monthly maintenance?"),
    t(8, "dealer", "12,000 monthly — security, cleaning, generator backup, all premium services."),
    t(9, "negotiator", "And the annual increment?"),
    t(10, "dealer", "Twelve percent yearly. Everyone charges this."),
    t(11, "negotiator", "Twelve is high; most agreements run five to ten. Would you cap it at eight if my client signs a three-year lease?"),
    t(12, "dealer", "Hmm. For a serious three-year party... I can do ten percent, final."),
    t(13, "negotiator", "Noted — 95,000 rent, 6 months advance, 142,500 commission, 12,000 maintenance, 10 percent increment. I'll log this quote."),
  ],
  firm: [
    t(1, "negotiator", "Assalam-o-Alaikum, I'm calling on behalf of a client for a 400 square foot ground-floor shop in Gulberg."),
    t(2, "dealer", "Hello, thank you for calling. Yes, I have a matching unit. Rent is 110,000 monthly."),
    t(3, "negotiator", "Could you itemise the full costs — advance, commission, maintenance, increment?"),
    t(4, "dealer", "Certainly. Two months advance so 220,000, one month commission 110,000, maintenance 5,000 monthly, and five percent annual increment."),
    t(5, "negotiator", "That's clear, thank you. Is there flexibility on the rent for a longer lease?"),
    t(6, "dealer", "On price, very little — it is market rate. For a three-year commitment I can waive half the commission."),
    t(7, "negotiator", "Half commission waived, so 55,000. Can you provide that in a written agreement?"),
    t(8, "dealer", "Yes, I can share a draft agreement today with every figure stated."),
    t(9, "negotiator", "Excellent. I'm logging: 110,000 rent, 2 months advance, 55,000 commission, 5,000 maintenance, 5 percent increment, written quote available."),
    t(10, "dealer", "Correct. I'll email the draft. Good day."),
  ],
  human: [
    t(1, "negotiator", "Assalam-o-Alaikum, I'm calling about a 400 square foot ground-floor shop in Gulberg for a client."),
    t(2, "dealer", "Walaikum salam. Yes, send me the requirements — I'll check with the owners and call you back."),
    t(3, "negotiator", "I'll share the spec. When should I follow up?"),
    t(4, "dealer", "Tomorrow afternoon. Khuda hafiz."),
  ],
};

export const MOCK_OUTCOMES: Record<Dealer["persona"], CallOutcome> = {
  stonewaller: "declined",
  lowballer: "quote",
  upseller: "quote",
  firm: "quote",
  human: "callback",
};

// total_first_year = 12*rent + advance_months*rent + commission + 12*maintenance
export const MOCK_QUOTES: Partial<Record<Dealer["persona"], Quote>> = {
  lowballer: {
    id: "quote_lowballer", call_id: "call_lowballer", dealer_id: "dealer_lowballer",
    monthly_rent: 65000, advance_months: 2, commission: 32500, maintenance: 3000,
    annual_increment_pct: 5, total_first_year: 998500, binding: false,
    notes: "No written agreement offered; wants token money first.",
  },
  upseller: {
    id: "quote_upseller", call_id: "call_upseller", dealer_id: "dealer_upseller",
    monthly_rent: 95000, advance_months: 6, commission: 142500, maintenance: 12000,
    annual_increment_pct: 10, total_first_year: 1996500, binding: false,
    notes: "Advance 6 months; increment talked down from 12% to 10%.",
  },
  firm: {
    id: "quote_firm", call_id: "call_firm", dealer_id: "dealer_firm",
    monthly_rent: 110000, advance_months: 2, commission: 55000, maintenance: 5000,
    annual_increment_pct: 5, total_first_year: 1655000, binding: true,
    notes: "Written draft agreement offered; half commission waived for 3-year lease.",
  },
};

// 0.5s of silent 16-bit mono PCM as a WAV blob URL — placeholder recording.
export function mockRecordingUrl(): string {
  const sampleRate = 8000;
  const samples = sampleRate / 2;
  const buf = new ArrayBuffer(44 + samples * 2);
  const v = new DataView(buf);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  v.setUint32(4, 36 + samples * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  writeStr(36, "data");
  v.setUint32(40, samples * 2, true);
  return URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
}
