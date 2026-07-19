"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import SpecCard from "@/components/dashboard/SpecCard";
import { listSpecsWithProgress } from "@/lib/api";
import type { SpecListEntry } from "@/lib/types";

export default function DashboardPage() {
  const [entries, setEntries] = useState<SpecListEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSpecsWithProgress()
      .then((e) => !cancelled && setEntries(e))
      .catch(() => !cancelled && setError("Could not load your rental searches. Check the backend and refresh."));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="anim-fade-up flex flex-1 flex-col">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-wider text-text-dim">Specs</p>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
            Your Rental Searches
          </h1>
          <p className="mt-1.5 max-w-lg text-sm text-text-secondary">
            Pick up where you left off, or start a new shop rental search.
          </p>
        </div>
        <Link
          href="/intake"
          className="tr inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 font-display text-sm font-semibold text-primary-fg hover:opacity-90 active:scale-[0.98]"
        >
          New spec
        </Link>
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-error-dim px-4 py-3 text-sm text-error">
          {error}
        </p>
      )}
      {!entries && !error && (
        <p className="rec-pulse py-12 text-center text-sm text-text-dim">Loading your rental searches...</p>
      )}
      {entries && entries.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 py-24 text-center">
          <p className="text-sm text-text-secondary">No rental searches yet — start your first shop rental search.</p>
          <Link
            href="/intake"
            className="tr inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-display text-sm font-semibold text-primary-fg hover:opacity-90 active:scale-[0.98]"
          >
            Start intake
          </Link>
        </div>
      )}
      {entries && entries.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {entries.map((entry) => (
            <SpecCard key={entry.item.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
