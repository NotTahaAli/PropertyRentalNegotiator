import type { JobSpec, ParsedDoc, IntakeSubmitResponse } from "./types";
import {
  MOCK_PARSE_RENT_AGREEMENT,
  MOCK_PARSE_REQUIREMENTS,
} from "./mocks";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
  const r = await fetch(`${BASE}/parse`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`parse failed: ${r.status}`);
  return r.json();
}

export async function submitSpec(spec: JobSpec): Promise<IntakeSubmitResponse> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 600));
    return { spec_id: "spec_mock_001", dealers_seeded: 4 };
  }
  const r = await fetch(`${BASE}/specs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!r.ok) throw new Error(`submit failed: ${r.status}`);
  return r.json();
}
