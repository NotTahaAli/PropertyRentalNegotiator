import type { ProgressState } from "@/lib/types";

export default function ProgressChip({ progress }: { progress: ProgressState }) {
  const { label, className } = (() => {
    switch (progress.kind) {
      case "intake":
        return { label: "Intake in progress", className: "bg-elevated text-text-dim" };
      case "ready_to_call":
        return { label: "Ready to call", className: "bg-info-dim text-info" };
      case "calling":
        return {
          label: `${progress.done} of ${progress.total} dealers done`,
          className: "bg-accent-dim text-accent",
        };
      case "report_ready":
        return { label: "Report ready", className: "bg-success-dim text-success" };
    }
  })();

  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide ${className}`}
    >
      {label}
    </span>
  );
}
