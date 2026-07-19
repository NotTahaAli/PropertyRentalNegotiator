import type { UiCallState } from "@/lib/types";

const BADGE: Record<UiCallState, { label: string; className: string; dot?: string }> = {
  idle: { label: "idle", className: "bg-elevated text-text-dim" },
  calling: { label: "calling", className: "bg-info-dim text-info", dot: "bg-info" },
  live: { label: "live", className: "bg-accent-dim text-accent", dot: "bg-accent" },
  done: { label: "done", className: "bg-success-dim text-success" },
  failed: { label: "failed", className: "bg-error-dim text-error" },
};

export default function StateBadge({ state }: { state: UiCallState }) {
  const b = BADGE[state];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide ${b.className}`}
    >
      {b.dot && <span className={`rec-pulse h-1.5 w-1.5 rounded-full ${b.dot}`} />}
      {b.label}
    </span>
  );
}
