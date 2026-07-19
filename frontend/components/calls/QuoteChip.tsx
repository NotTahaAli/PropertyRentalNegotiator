import type { Quote } from "@/lib/types";

const fmt = new Intl.NumberFormat("en-PK");

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-border/50 py-1.5 last:border-0">
      <span className="text-xs text-text-dim">{label}</span>
      <span className="font-mono text-xs tabular-nums text-text">{value}</span>
    </div>
  );
}

export default function QuoteChip({ quote, live = false }: { quote: Quote; live?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-elevated p-4">
      <div className="flex items-center justify-between">
        <p className="font-display text-sm font-semibold text-text">{quote.property_ref ?? "Logged quote"}</p>
        <div className="flex gap-1.5">
          {live && (
            <span className="rec-pulse rounded-md bg-accent-dim px-2 py-0.5 font-mono text-[10px] text-accent">
              live
            </span>
          )}
          {quote.binding && (
            <span className="rounded-md bg-success-dim px-2 py-0.5 font-mono text-[10px] text-success">
              written
            </span>
          )}
          {quote.flagged && (
            <span className="rounded-md bg-error-dim px-2 py-0.5 font-mono text-[10px] text-error">
              flagged
            </span>
          )}
        </div>
      </div>

      <div className="mt-2">
        <Row label="Monthly rent" value={`PKR ${fmt.format(quote.monthly_rent)}`} />
        {quote.advance_months != null && (
          <Row label="Advance" value={`${quote.advance_months} months`} />
        )}
        {quote.commission != null && (
          <Row label="Commission" value={`PKR ${fmt.format(quote.commission)}`} />
        )}
        {quote.maintenance != null && (
          <Row label="Maintenance / mo" value={`PKR ${fmt.format(quote.maintenance)}`} />
        )}
        {quote.annual_increment_pct != null && (
          <Row label="Annual increment" value={`${quote.annual_increment_pct}%`} />
        )}
        {quote.other_fees &&
          Object.entries(quote.other_fees).map(([k, v]) => (
            <Row key={k} label={k} value={`PKR ${fmt.format(v)}`} />
          ))}
      </div>

      <div className="mt-3 rounded-lg bg-accent-dim p-3">
        <p className="text-xs text-text-secondary">Total first year</p>
        <p className="mt-0.5 font-display text-lg font-bold text-accent">
          PKR {fmt.format(quote.total_first_year)}
        </p>
      </div>

      {quote.notes && <p className="mt-2.5 text-xs text-text-secondary">{quote.notes}</p>}
      {quote.flag_reason && (
        <p className="mt-1.5 text-xs text-error">{quote.flag_reason}</p>
      )}
    </div>
  );
}
