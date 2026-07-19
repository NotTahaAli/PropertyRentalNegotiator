import CitationLink from "./CitationLink";
import FlagChip from "./FlagChip";
import PriceCell from "./PriceCell";
import type { ReportRow } from "@/lib/types";

interface RankedTableProps {
  specId: string;
  rows: ReportRow[];
  recommendedRowId: string | null; // null when no dealer produced a quote
}

export default function RankedTable({ specId, rows, recommendedRowId }: RankedTableProps) {
  return (
    <div className="flex flex-col gap-3">
      {rows.map((row) => {
        const recommended = row.row_id === recommendedRowId;
        return (
          <div
            key={row.row_id}
            className={`tr rounded-xl border bg-surface p-4 sm:p-5 ${
              recommended ? "border-accent/60" : "border-border"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-display text-sm font-semibold ${
                    row.rank === null
                      ? "bg-elevated text-text-dim"
                      : recommended
                        ? "bg-accent text-bg"
                        : "bg-elevated text-text"
                  }`}
                >
                  {row.rank ?? "—"}
                </span>
                <div>
                  <p className="font-display text-sm font-semibold text-text">
                    {row.dealer_name}
                    {row.property_ref && (
                      <span className="ml-1.5 font-normal text-text-dim">— {row.property_ref}</span>
                    )}
                  </p>
                  {row.outcome === "declined" ? (
                    <p className="text-xs text-error">Declined — unit not available</p>
                  ) : recommended ? (
                    <p className="text-xs text-accent">Recommended</p>
                  ) : null}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex flex-col items-end gap-0.5">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-xs text-text-dim">Term:</span>
                    <PriceCell amount={row.total_term ?? row.quote?.total_term ?? row.quote?.total_first_year ?? null} emphasize={recommended} />
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-xs text-text-dim">1st yr:</span>
                    <PriceCell amount={row.quote?.total_first_year ?? null} emphasize={false} />
                  </div>
                </div>
                <CitationLink specId={specId} callNumber={row.call_number} line={row.citation_line} />
              </div>
            </div>
            {row.quote?.flagged && row.quote.flag_reason && (
              <div className="mt-3">
                <FlagChip reason={row.quote.flag_reason} />
              </div>
            )}
            {row.meets_deadline === false && (
              <div className="mt-2 text-xs text-error font-medium">Misses delivery deadline</div>
            )}
            {row.meets_deadline === true && (
              <div className="mt-2 text-xs text-success font-medium">Confirmed delivery</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
