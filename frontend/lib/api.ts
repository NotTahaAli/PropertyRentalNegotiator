import type {
  CallRow,
  CallStartResponse,
  Dealer,
  IntakeSubmitResponse,
  JobSpec,
  ParsedDoc,
  Quote,
} from "./types";
import {
  MOCK_DEALERS,
  MOCK_PARSE_RENT_AGREEMENT,
  MOCK_PARSE_REQUIREMENTS,
} from "./mocks";
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
    return { spec_id: "spec_mock_001", dealers_seeded: 4 };
  }
  // Backend SpecCreate wants {vertical, status, spec_json, confirmed};
  // it returns the full spec row and does not seed dealers (see TODO.md).
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
  return { spec_id: row.id, dealers_seeded: 0 };
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

export async function startCall(
  specId: string,
  dealerId: string,
  mode: "bridge" | "roleplay" = "bridge"
): Promise<CallStartResponse> {
  const r = await fetch(`${BASE}/calls/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ spec_id: specId, dealer_id: dealerId, round: 1, mode }),
  });
  if (!r.ok) throw new Error(`start call failed: ${r.status}`);
  return r.json();
}

export async function getCall(callId: string): Promise<CallRow> {
  return getJson(`/calls/${encodeURIComponent(callId)}`);
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
