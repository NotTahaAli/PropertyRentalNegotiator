import type { JobSpec, ParsedDoc, IntakeSubmitResponse } from "./types";
import {
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
  return { spec_id: row.id, dealers_seeded: row.dealers_seeded ?? 0 };
}
