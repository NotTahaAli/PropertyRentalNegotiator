"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import RankedTable from "@/components/report/RankedTable";
import RecommendationBlock from "@/components/report/RecommendationBlock";
import Button from "@/components/ui/Button";
import BenchmarkBadge from "@/components/spec/BenchmarkBadge";
import { getReport, getSpec, reflagSpec } from "@/lib/api";
import type { Benchmark, Report } from "@/lib/types";

export default function ReportPage() {
  const params = useParams<{ spec_id: string }>();
  const specId = params.spec_id;
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);
  const [recheckNote, setRecheckNote] = useState<string | null>(null);
  const [benchmark, setBenchmark] = useState<Benchmark | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    getSpec(specId)
      .then((s) => !cancelled && setBenchmark(s.benchmark_json ?? null))
      .catch(() => !cancelled && setBenchmark(null));
    return () => {
      cancelled = true;
    };
  }, [specId]);

  const load = useCallback(
    (isCancelled?: () => boolean) =>
      getReport(specId)
        .then((r) => {
          if (!isCancelled?.()) setReport(r);
        })
        .catch(() => {
          if (!isCancelled?.())
            setError(
              "Report not available — this spec has no calls yet, or the backend is unreachable."
            );
        }),
    [specId]
  );

  useEffect(() => {
    let cancelled = false;
    load(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [load]);

  // Red-flag verdicts can be stale: a quote logged before the Tavily benchmark
  // landed was judged against the config fallback. Re-running the rules before
  // trusting the ranking is cheap, and can unflag as well as flag.
  async function recheckFlags() {
    setRechecking(true);
    setRecheckNote(null);
    try {
      const { checked, updated } = await reflagSpec(specId);
      await load();
      setRecheckNote(
        updated === 0
          ? `Re-checked ${checked} quote${checked === 1 ? "" : "s"} — no changes.`
          : `Re-checked ${checked} quotes — ${updated} verdict${updated === 1 ? "" : "s"} updated.`
      );
    } catch {
      setRecheckNote("Could not re-check flags.");
    } finally {
      setRechecking(false);
    }
  }

  return (
    <div className="anim-fade-up flex flex-1 flex-col">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4 print:hidden">
        <div>
          <p className="font-mono text-xs tracking-wider text-text-dim">Spec {specId}</p>
          <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
            Report
          </h2>
          <p className="mt-1.5 max-w-lg text-sm text-text-secondary">
            Every dealer, ranked by total term cost, with red flags and
            transcript evidence for the recommended deal.
          </p>
          <div className="mt-3 print:hidden">
            <BenchmarkBadge benchmark={benchmark} />
          </div>
        </div>
        {report && (
          <div className="flex flex-col items-end gap-1.5">
            <Button variant="secondary" onClick={recheckFlags} disabled={rechecking}>
              {rechecking ? "Re-checking..." : "Re-check flags"}
            </Button>
            {recheckNote && (
              <p className="text-xs text-text-dim" role="status">
                {recheckNote}
              </p>
            )}
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-error-dim px-4 py-3 text-sm text-error">
          {error}
        </p>
      )}
      {!report && !error && (
        <p className="rec-pulse py-12 text-center text-sm text-text-dim">Loading report...</p>
      )}

      {report && (
        <div className="flex flex-col gap-6">
          <RecommendationBlock specId={specId} report={report} />
          <RankedTable specId={specId} rows={report.rows} recommendedRowId={report.recommended_row_id} />
        </div>
      )}
    </div>
  );
}
