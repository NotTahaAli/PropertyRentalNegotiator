import type { CallRow, Dealer, ProgressState, SpecListItem } from "./types";

// Single source of truth for the dashboard's progress chip — used by both
// mock and real data paths so they can't drift into different logic.
export function deriveProgress(
  spec: SpecListItem,
  dealers: Dealer[],
  calls: CallRow[]
): ProgressState {
  if (!spec.confirmed) return { kind: "intake" };
  if (dealers.length === 0) return { kind: "ready_to_call" };

  const latestByDealer = new Map<string, CallRow>();
  for (const c of calls) {
    const prev = latestByDealer.get(c.dealer_id);
    if (!prev || c.round >= prev.round) latestByDealer.set(c.dealer_id, c);
  }
  const done = dealers.filter((d) => {
    const c = latestByDealer.get(d.id);
    return c && (c.status === "completed" || c.status === "failed");
  }).length;

  if (done === 0) return { kind: "ready_to_call" };
  if (done < dealers.length) return { kind: "calling", done, total: dealers.length };
  return { kind: "report_ready" };
}
