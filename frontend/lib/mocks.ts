import type {
  CallOutcome,
  CallRow,
  Dealer,
  JobSpec,
  ParsedDoc,
  Quote,
  Report,
  SpecListItem,
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
  {
    id: "dealer_tavily_alpha", spec_id: "spec_mock_001", name: "Alpha Estate & Builders",
    persona: "human", phone_label: "https://alpha-estate.pk", source: "tavily",
    phone: "0321-4567890", rating: 4.2, rating_source: "Google",
  },
];

// "Search more dealers" — canned result for a demo click, not already in
// MOCK_DEALERS. Real endpoint would return genuinely new businesses; rating
// omitted on one to keep "no rating" a visibly normal state, not an edge case.
export const MOCK_DISCOVERED_DEALERS: Dealer[] = [
  {
    id: "dealer_tavily_beta", spec_id: "spec_mock_001", name: "Beta Commercial Properties",
    persona: "human", phone_label: "https://beta-properties.pk", source: "tavily",
    phone: "0300-1122334", rating: 3.8, rating_source: "Google",
  },
  {
    id: "dealer_tavily_gamma", spec_id: "spec_mock_001", name: "Gulberg Shop Consultants",
    persona: "human", phone_label: "Gulberg III, Lahore", source: "tavily",
  },
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
    t(2, "dealer", "Good day! I actually have two matching shops right now — Shop 2 and Shop 7. Shop 2's base rent is 95,000 monthly."),
    t(3, "negotiator", "What advance do you require on Shop 2?"),
    t(4, "dealer", "Six months advance, 570,000. Prime location, this is normal."),
    t(5, "negotiator", "Six months is above the usual two to three. What about commission?"),
    t(6, "dealer", "One and a half month commission, 142,500. Standard practice."),
    t(7, "negotiator", "Monthly maintenance?"),
    t(8, "dealer", "12,000 monthly — security, cleaning, generator backup, all premium services."),
    t(9, "negotiator", "And the annual increment on Shop 2?"),
    t(10, "dealer", "Twelve percent yearly. Everyone charges this."),
    t(11, "negotiator", "Twelve is high; most agreements run five to ten. Would you cap it at eight if my client signs a three-year lease?"),
    t(12, "dealer", "Hmm. For a serious three-year party on Shop 2... I can do ten percent, final."),
    t(13, "negotiator", "Noted for Shop 2 — 95,000 rent, 6 months advance, 142,500 commission, 12,000 maintenance, 10 percent increment. Now what about Shop 7?"),
    t(14, "dealer", "Shop 7 is smaller — base rent 80,000 monthly, same six months advance, so 480,000. Commission 120,000, maintenance 10,000, same ten percent increment for a three-year lease."),
    t(15, "negotiator", "Understood. Logging both quotes: Shop 2 and Shop 7, each with the terms just given."),
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

// Round 2 = leverage round (get_leverage cites round-1's real logged bids).
// Lowballer had the lowest total_first_year (998,500) of any real quote, so
// that's what Firm-but-Fair gets confronted with — master plan §414's
// headline demo moment: price moves because of leverage, not a script.
export const MOCK_TRANSCRIPTS_ROUND2: Partial<Record<Dealer["persona"], TranscriptLine[]>> = {
  stonewaller: [
    t(1, "negotiator", "Following up again about the Gulberg shop — has anything changed on your side?"),
    t(2, "dealer", "That one, still with the other party, I told you."),
    t(3, "negotiator", "Understood. I'll take this as a final decline then."),
    t(4, "dealer", "Yes, decline. Khuda hafiz."),
  ],
  lowballer: [
    t(1, "negotiator", "Following up — I have another offer close to yours already. Any room to move further?"),
    t(2, "dealer", "Ji, this price is already the best in the market, nothing more to reduce."),
    t(3, "negotiator", "Understood, I'll log the same terms as final."),
  ],
  upseller: [
    t(1, "negotiator", "Following up with a documented lower offer from another dealer — any room to match it?"),
    t(2, "dealer", "I already gave my best for a three-year commitment, ten percent final. Can't go below that."),
    t(3, "negotiator", "Understood, logging the same quote as final."),
  ],
  firm: [
    t(1, "negotiator", "I have a documented offer at 65,000 monthly, all-in, for a comparable shop — can you match it?"),
    t(2, "dealer", "That's below what I quoted, but for a genuine competing offer I can adjust. I'll bring the rent down and waive the commission entirely."),
    t(3, "negotiator", "So the commission is waived — what's the revised monthly rent?"),
    t(4, "dealer", "I can do 100,000, no commission, everything else stays as agreed."),
    t(5, "negotiator", "Noted — 100,000 rent, 2 months advance, commission waived, 5,000 maintenance, 5 percent increment. Logging the updated quote."),
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
// A dealer may have multiple quotes (one per matching property, discriminated by
// property_ref) — Upseller is the demo case, with two shops on the same call.
export const MOCK_QUOTES: Partial<Record<Dealer["persona"], Quote[]>> = {
  lowballer: [
    {
      id: "quote_lowballer", call_id: "call_lowballer", dealer_id: "dealer_lowballer",
      monthly_rent: 65000, advance_months: 2, commission: 32500, maintenance: 3000,
      annual_increment_pct: 5, total_first_year: 998500, binding: false,
      notes: "No written agreement offered; wants token money first.",
      flagged: true,
      flag_reason: "Quoted ~40% under benchmark with no written agreement offered — confirm scope before trusting this number.",
      property_ref: null,
    },
  ],
  upseller: [
    {
      id: "quote_upseller_shop2", call_id: "call_upseller", dealer_id: "dealer_upseller",
      monthly_rent: 95000, advance_months: 6, commission: 142500, maintenance: 12000,
      annual_increment_pct: 10, total_first_year: 1996500, binding: false,
      notes: "Advance 6 months; increment talked down from 12% to 10%.",
      property_ref: "Shop 2",
    },
    {
      id: "quote_upseller_shop7", call_id: "call_upseller", dealer_id: "dealer_upseller",
      monthly_rent: 80000, advance_months: 6, commission: 120000, maintenance: 10000,
      annual_increment_pct: 10, total_first_year: 1680000, binding: false,
      notes: "Smaller unit; same advance/increment terms as Shop 2.",
      property_ref: "Shop 7",
    },
  ],
  firm: [
    {
      id: "quote_firm", call_id: "call_firm", dealer_id: "dealer_firm",
      monthly_rent: 110000, advance_months: 2, commission: 55000, maintenance: 5000,
      annual_increment_pct: 5, total_first_year: 1655000, binding: true,
      notes: "Written draft agreement offered; half commission waived for 3-year lease.",
      property_ref: null,
    },
  ],
};

// Round 2 quotes — only where the number actually changes (Firm-but-Fair,
// the leverage concession). Lowballer/Upseller hold their round-1 quote(s)
// (nothing left to concede), so they aren't overridden here.
export const MOCK_QUOTES_ROUND2: Partial<Record<Dealer["persona"], Quote[]>> = {
  firm: [
    {
      id: "quote_firm_r2", call_id: "call_firm_r2", dealer_id: "dealer_firm",
      monthly_rent: 100000, advance_months: 2, commission: 0, maintenance: 5000,
      annual_increment_pct: 5, total_first_year: 1460000, binding: true,
      notes: "Round 2: matched a documented 65,000 competing offer — rent trimmed 110k→100k, commission fully waived.",
      property_ref: null,
    },
  ],
};

// ── K10 Report mock — final-round-per-dealer(-property) snapshot of the
// 2-round demo. call_number = MOCK_DEALERS index+1 (stonewaller=1, lowballer=2,
// upseller=3, firm=4); citation_line points into MOCK_TRANSCRIPTS_ROUND2 for the
// dealers that reached round 2. Stonewaller never gets a round-2 callback — a
// dealer who already said the unit is rented doesn't get redialed — so its
// final round is 1, per the round-1 decline transcript. Upseller quoted two
// shops on the same call, so it contributes two ranked rows, same as the
// backend's per-property grouping would.
const upsellerShop2 = MOCK_QUOTES.upseller?.[0] ?? null;
const upsellerShop7 = MOCK_QUOTES.upseller?.[1] ?? null;

export const MOCK_REPORT: Report = {
  spec_id: "spec_mock_001",
  rows: [
    {
      dealer_id: "dealer_firm", dealer_name: "Firm Dealer", persona: "firm",
      property_ref: null, row_id: "dealer_firm:",
      rank: 1, quote: MOCK_QUOTES_ROUND2.firm?.[0] ?? null, round: 2, outcome: "quote",
      call_number: 4, citation_line: 4, recording_url: mockRecordingUrl(),
    },
    {
      dealer_id: "dealer_upseller", dealer_name: "Upseller Dealer", persona: "upseller",
      property_ref: "Shop 7", row_id: "dealer_upseller:Shop 7",
      rank: 2, quote: upsellerShop7, round: 2, outcome: "quote",
      call_number: 3, citation_line: 14, recording_url: mockRecordingUrl(),
    },
    {
      dealer_id: "dealer_upseller", dealer_name: "Upseller Dealer", persona: "upseller",
      property_ref: "Shop 2", row_id: "dealer_upseller:Shop 2",
      rank: 3, quote: upsellerShop2, round: 2, outcome: "quote",
      call_number: 3, citation_line: 2, recording_url: mockRecordingUrl(),
    },
    {
      dealer_id: "dealer_lowballer", dealer_name: "Lowballer Dealer", persona: "lowballer",
      property_ref: null, row_id: "dealer_lowballer:",
      rank: 4, quote: MOCK_QUOTES.lowballer?.[0] ?? null, round: 2, outcome: "quote",
      call_number: 2, citation_line: 1, recording_url: mockRecordingUrl(),
    },
    {
      dealer_id: "dealer_stonewaller", dealer_name: "Stonewaller Dealer", persona: "stonewaller",
      property_ref: null, row_id: "dealer_stonewaller:",
      rank: null, quote: null, round: 1, outcome: "declined",
      call_number: 1, citation_line: 1, recording_url: mockRecordingUrl(),
    },
  ],
  recommended_dealer_id: "dealer_firm",
  recommended_row_id: "dealer_firm:",
  recommendation_text:
    "Firm-but-Fair offers the best verified deal at PKR 1,460,000 for the first year. " +
    "On the first call it quoted a fair, fully itemised 110,000/month with standard terms. " +
    "On the follow-up call, once the Negotiator raised a real logged offer of 65,000/month from " +
    "another dealer, Firm-but-Fair matched it in spirit — trimming rent to 100,000/month and " +
    "fully waiving the commission — a concession only possible because of leverage the agent " +
    "actually gathered, not a scripted discount. Lowballer's headline number is lower, but it's " +
    "flagged: quoted far enough under benchmark to warrant scrutiny, with no written agreement " +
    "offered, so it is not recommended as the top pick despite the number.",
};

// ── Past-calls dashboard mock — raw fixtures, run through the same
// deriveProgress() the real data path uses (lib/dashboard.ts), not a
// hardcoded status. Spec 3 deliberately reuses MOCK_REPORT.spec_id/dealers
// so "View report" from the dashboard opens the real mock report.
export const MOCK_SPEC_FIXTURES: { item: SpecListItem; dealers: Dealer[]; calls: CallRow[] }[] = [
  {
    item: {
      id: "spec_mock_002",
      created_at: "2026-07-18T09:15:00Z",
      confirmed: false,
      spec: { location: "DHA Phase 5, Lahore", business_type: "cafe" },
    },
    dealers: [],
    calls: [],
  },
  {
    item: {
      id: "spec_mock_003",
      created_at: "2026-07-18T14:40:00Z",
      confirmed: true,
      spec: { location: "Bahria Town, Rawalpindi", business_type: "pharmacy" },
    },
    dealers: [
      { id: "d3_stonewaller", spec_id: "spec_mock_003", name: "Stonewaller Dealer", persona: "stonewaller", source: "seed" },
      { id: "d3_lowballer", spec_id: "spec_mock_003", name: "Lowballer Dealer", persona: "lowballer", source: "seed" },
      { id: "d3_upseller", spec_id: "spec_mock_003", name: "Upseller Dealer", persona: "upseller", source: "seed" },
      { id: "d3_firm", spec_id: "spec_mock_003", name: "Firm Dealer", persona: "firm", source: "seed" },
    ],
    calls: [
      { id: "c3_1", spec_id: "spec_mock_003", dealer_id: "d3_stonewaller", round: 1, status: "completed", outcome: "declined" },
      { id: "c3_2", spec_id: "spec_mock_003", dealer_id: "d3_lowballer", round: 1, status: "completed", outcome: "quote" },
    ],
  },
  {
    item: {
      id: MOCK_REPORT.spec_id,
      created_at: "2026-07-17T11:00:00Z",
      confirmed: true,
      spec: { location: MOCK_SPEC.location, business_type: MOCK_SPEC.business_type },
      // No source_url yet — (b) from the plan: honest "no citation" state,
      // ships until the backend captures one alongside the two numbers.
      benchmark_json: { per_sqft_low: 180, per_sqft_high: 450 },
    },
    dealers: MOCK_DEALERS.filter((d) => d.persona !== "human"),
    // A dealer can contribute more than one report row (multiple properties)
    // but they share one underlying call — dedupe by dealer_id so the call
    // list doesn't produce two rows with the same id.
    calls: [...new Map(MOCK_REPORT.rows.map((r) => [r.dealer_id, r])).values()].map((r) => ({
      id: `call_${r.dealer_id}`,
      spec_id: MOCK_REPORT.spec_id,
      dealer_id: r.dealer_id,
      round: r.round,
      status: "completed" as const,
      outcome: r.outcome,
    })),
  },
];

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
