import type {
  CallRow,
  CallStartResponse,
  Dealer,
  IntakeSubmitResponse,
  JobSpec,
  ParsedDoc,
  Persona,
  Quote,
  Report,
  SpecListEntry,
  SpecListItem,
} from "./types";
import {
  MOCK_DEALERS,
  MOCK_PARSE_RENT_AGREEMENT,
  MOCK_PARSE_REQUIREMENTS,
  MOCK_REPORT,
  MOCK_SPEC_FIXTURES,
} from "./mocks";
import { deriveProgress } from "./dashboard";
import { getAccessToken } from "@/components/auth/AuthProvider";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function parseDoc(
  file: File,
  kind: ParsedDoc["kind"]
): Promise<ParsedDoc> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 900));
    return kind === "rent_agreement"
      ? MOCK_PARSE_RENT_AGREEMENT
      : MOCK_PARSE_REQUIREMENTS;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("kind", kind);
  const r = await fetch(`${BASE}/parse`, {
    method: "POST",
    headers: await authHeaders(),
    body: fd,
  });
  if (!r.ok) throw new Error(`parse failed: ${r.status}`);
  return r.json();
}

export async function submitSpec(spec: JobSpec): Promise<IntakeSubmitResponse> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 600));
    return { spec_id: "spec_mock_001", dealers_seeded: 4, dealers_discovered: 1 };
  }
  // Backend SpecCreate wants {vertical, status, spec_json, confirmed};
  // it returns the spec row plus dealers_seeded (one dealer per persona).
  const r = await fetch(`${BASE}/specs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      vertical: spec.vertical,
      status: "confirmed",
      spec_json: spec,
      confirmed: true,
    }),
  });
  if (!r.ok) throw new Error(`submit failed: ${r.status}`);
  const row = await r.json();
  return {
    spec_id: row.id,
    dealers_seeded: row.dealers_seeded ?? 0,
    dealers_discovered: row.dealers_discovered ?? 0,
  };
}

// ── K9 Call Center (mock lifecycle itself lives in lib/useCallCenter.ts) ──

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return r.json();
}

export async function listDealers(specId: string): Promise<Dealer[]> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400));
    return MOCK_DEALERS;
  }
  return getJson(`/dealers?spec_id=${encodeURIComponent(specId)}`);
}

export async function updateDealer(
  dealerId: string,
  persona: Persona
): Promise<Dealer> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 300));
    const dealer = MOCK_DEALERS.find((d) => d.id === dealerId);
    if (!dealer) throw new Error("dealer not found");
    dealer.persona = persona;
    return { ...dealer };
  }
  const r = await fetch(`${BASE}/dealers/${encodeURIComponent(dealerId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ persona }),
  });
  if (!r.ok) throw new Error(`update dealer failed: ${r.status}`);
  return r.json();
}

export async function startCall(
  specId: string,
  dealerId: string,
  mode: "bridge" | "roleplay" = "bridge",
  round: number = 1
): Promise<CallStartResponse> {
  const r = await fetch(`${BASE}/calls/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ spec_id: specId, dealer_id: dealerId, round, mode }),
  });
  if (!r.ok) throw new Error(`start call failed: ${r.status}`);
  return r.json();
}

export async function getCall(callId: string): Promise<CallRow> {
  return getJson(`/calls/${encodeURIComponent(callId)}`);
}

export async function endCall(callId: string): Promise<void> {
  const r = await fetch(`${BASE}/calls/${encodeURIComponent(callId)}/end`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`end call failed: ${r.status}`);
}

export async function getRecordingUrl(callId: string): Promise<string | null> {
  const res = await getJson<{ recording_url: string | null }>(
    `/calls/${encodeURIComponent(callId)}/recording`
  );
  return res.recording_url;
}

export async function listQuotes(callId: string): Promise<Quote[]> {
  return getJson(`/quotes?call_id=${encodeURIComponent(callId)}`);
}

export async function listCalls(specId: string): Promise<CallRow[]> {
  return getJson(`/calls?spec_id=${encodeURIComponent(specId)}`);
}

// ── Past-calls dashboard (/) ──

export async function listSpecs(): Promise<SpecListItem[]> {
  const rows = await getJson<
    { id: string; created_at?: string; confirmed: boolean; spec_json: Partial<JobSpec> }[]
  >("/specs");
  return rows.map((row) => ({
    id: row.id,
    created_at: row.created_at,
    confirmed: row.confirmed,
    spec: row.spec_json,
  }));
}

export async function getSpec(specId: string): Promise<SpecListItem> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 200));
    const fixture = MOCK_SPEC_FIXTURES.find((f) => f.item.id === specId);
    if (fixture) return fixture.item;
    return { id: specId, confirmed: true, spec: {} };
  }
  const row = await getJson<{ id: string; created_at?: string; confirmed: boolean; spec_json: Partial<JobSpec> }>(
    `/specs/${encodeURIComponent(specId)}`
  );
  return { id: row.id, created_at: row.created_at, confirmed: row.confirmed, spec: row.spec_json };
}

export async function listSpecsWithProgress(): Promise<SpecListEntry[]> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400));
    return MOCK_SPEC_FIXTURES.map((f) => ({
      item: f.item,
      progress: deriveProgress(f.item, f.dealers, f.calls),
    }));
  }
  const specs = await listSpecs();
  return Promise.all(
    specs.map(async (item) => {
      const [dealers, calls] = await Promise.all([listDealers(item.id), listCalls(item.id)]);
      return { item, progress: deriveProgress(item, dealers, calls) };
    })
  );
}

// ── K10 Report ──

export async function getReport(specId: string): Promise<Report> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 500));
    return MOCK_REPORT;
  }
  return getJson(`/report/${encodeURIComponent(specId)}`);
}

/** Re-runs the red-flag rules over every quote of a spec against the current
 * benchmark. May unflag: quotes judged on a fallback benchmark, or flagged by a
 * client-supplied value, get corrected. Called before ranking so the report
 * never orders rows on a stale verdict. */
export async function reflagSpec(
  specId: string
): Promise<{ checked: number; updated: number }> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400));
    return { checked: MOCK_REPORT.rows.length, updated: 0 };
  }
  const r = await fetch(`${BASE}/specs/${encodeURIComponent(specId)}/reflag`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`reflag failed: ${r.status}`);
  return r.json();
}
