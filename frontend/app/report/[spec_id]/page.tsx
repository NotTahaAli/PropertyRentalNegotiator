"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import RankedTable from "@/components/report/RankedTable";
import RecommendationBlock from "@/components/report/RecommendationBlock";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";

export default function ReportPage() {
  const params = useParams<{ spec_id: string }>();
  const specId = params.spec_id;
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getReport(specId)
      .then((r) => !cancelled && setReport(r))
      .catch(() =>
        !cancelled &&
        setError(
          "Report not available yet — the backend report generator (K10) hasn't shipped, or this spec has no calls yet."
        )
      );
    return () => {
      cancelled = true;
    };
  }, [specId]);

  return (
    <div className="anim-fade-up flex flex-1 flex-col">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4 print:hidden">
        <div>
          <p className="font-mono text-xs tracking-wider text-text-dim">Spec {specId}</p>
          <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
            Report
          </h2>
          <p className="mt-1.5 max-w-lg text-sm text-text-secondary">
            Every dealer, ranked by total first-year cost, with red flags and
            transcript evidence for the recommended deal.
          </p>
        </div>
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
          <RankedTable specId={specId} rows={report.rows} recommendedDealerId={report.recommended_dealer_id} />
        </div>
      )}
    </div>
  );
}
