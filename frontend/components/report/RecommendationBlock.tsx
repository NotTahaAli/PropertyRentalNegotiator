import CitationLink from "./CitationLink";
import type { Report } from "@/lib/types";

export default function RecommendationBlock({ specId, report }: { specId: string; report: Report }) {
  const row = report.rows.find((r) => r.dealer_id === report.recommended_dealer_id);

  return (
    <div className="rounded-xl border border-accent/60 bg-accent-dim p-5 sm:p-6">
      <p className="font-mono text-[10px] uppercase tracking-wide text-accent">
        Recommended deal
      </p>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">{report.recommendation_text}</p>
      {row && (
        <div className="mt-4">
          <CitationLink specId={specId} callNumber={row.call_number} line={row.citation_line} />
        </div>
      )}
    </div>
  );
}
