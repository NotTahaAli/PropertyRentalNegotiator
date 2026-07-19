"use client";

import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import ProgressChip from "./ProgressChip";
import type { SpecListEntry } from "@/lib/types";

function actionFor(progress: SpecListEntry["progress"], specId: string) {
  switch (progress.kind) {
    case "intake":
      return { label: "Continue intake", href: "/intake" };
    case "ready_to_call":
    case "calling":
      return { label: "Go to calls", href: `/calls/${specId}` };
    case "report_ready":
      return { label: "View report", href: `/report/${specId}` };
  }
}

export default function SpecCard({ entry }: { entry: SpecListEntry }) {
  const router = useRouter();
  const { item, progress } = entry;
  const action = actionFor(progress, item.id);
  const updated = item.created_at
    ? new Date(item.created_at).toLocaleDateString("en-PK", { year: "numeric", month: "short", day: "numeric" })
    : null;

  return (
    <div className="card-hover flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-display text-base font-semibold text-text">
            {item.spec.location || "Untitled spec"}
          </p>
          {item.spec.business_type && (
            <p className="mt-0.5 truncate text-sm text-text-secondary">{item.spec.business_type}</p>
          )}
        </div>
        <ProgressChip progress={progress} />
      </div>
      {updated && <p className="font-mono text-[10px] uppercase tracking-wide text-text-dim">{updated}</p>}
      <Button className="self-start px-4 py-1.5 text-xs" onClick={() => router.push(action.href)}>
        {action.label}
      </Button>
    </div>
  );
}
