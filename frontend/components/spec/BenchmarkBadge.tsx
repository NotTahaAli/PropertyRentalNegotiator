import type { Benchmark } from "@/lib/types";

const fmt = new Intl.NumberFormat("en-PK");

// Renders nothing when benchmark_json is null — Tavily failed, timed out, or
// hasn't run yet. source_url is undefined until the backend captures one
// (see CLAUDE.md handoff spec); never fabricate a citation in its place.
export default function BenchmarkBadge({ benchmark }: { benchmark: Benchmark | null | undefined }) {
  if (!benchmark) return null;
  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs">
      <span className="text-text-secondary">Market estimate (AI-researched):</span>
      <span className="font-mono font-medium text-text">
        PKR {fmt.format(benchmark.per_sqft_low)}–{fmt.format(benchmark.per_sqft_high)}/sqft/mo
      </span>
      {benchmark.source_url ? (
        <a
          href={benchmark.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="tr text-text-dim hover:text-accent"
          title="Source"
        >
          [source]
        </a>
      ) : (
        <span className="text-text-dim" title="Source citation not yet captured">
          (no source cited)
        </span>
      )}
    </div>
  );
}
