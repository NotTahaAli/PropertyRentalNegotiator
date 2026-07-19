"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import NavAuth from "@/components/auth/NavAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import SpecCard from "@/components/dashboard/SpecCard";
import { listSpecsWithProgress } from "@/lib/api";
import type { SpecListEntry } from "@/lib/types";

const FEATURES = [
  {
    num: "01",
    title: "Estimator",
    desc: "Voice agent interviews you to gather every requirement — area, budget, location, timeline.",
    accent: "text-accent",
  },
  {
    num: "02",
    title: "Caller",
    desc: "AI contacts real property dealers across the city, negotiates rates, and extracts itemised quotes.",
    accent: "text-info",
  },
  {
    num: "03",
    title: "Closer",
    desc: "Ranked results delivered with full breakdowns. Pick the best deal, ready to sign.",
    accent: "text-success",
  },
] as const;

export default function Home() {
  const { user, loading } = useAuth();

  // Reuses Protected's own loading skeleton verbatim — same pattern used
  // everywhere else auth resolves, and gates both branches below so neither
  // the hero nor the dashboard mounts (and no dashboard fetch fires) until
  // auth state is known. No flash either direction.
  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24">
        <span className="rec-pulse font-mono text-xs text-text-dim">Checking session...</span>
      </div>
    );
  }

  return user ? <DashboardContent /> : <MarketingHero />;
}

function MarketingHero() {
  return (
    <div className="flex min-h-screen flex-col bg-bg ambient-glow">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <span className="font-display text-sm font-semibold tracking-tight text-text">
          PropertyRentalNegotiator
        </span>
        <div className="flex items-center gap-4">
          <span className="font-mono text-xs text-text-dim">Hack-Nation · 01</span>
          <NavAuth />
        </div>
      </nav>

      <main className="flex flex-1 flex-col lg:flex-row">
        <div className="flex flex-1 flex-col justify-center px-6 py-16 sm:px-10 lg:px-16 xl:px-24">
          <div className="max-w-xl">
            <p className="anim-fade-up font-mono text-xs text-text-dim tracking-wider">
              Property rental intelligence
            </p>

            <h1 className="anim-fade-up delay-75 mt-5 font-display text-5xl font-bold leading-[1.05] tracking-tight text-text sm:text-6xl xl:text-7xl">
              The <span className="text-accent">Negotiator</span>
              <span className="text-text-dim">.</span>
            </h1>

            <p className="anim-fade-up delay-150 mt-6 max-w-md text-base leading-relaxed text-text-secondary sm:text-lg">
              Voice agents call Pakistani property dealers, extract itemised
              rent quotes, and rank them — so you don&apos;t have to.
            </p>

            <div className="anim-fade-up delay-225 mt-10 flex items-center gap-4">
              <Link
                href="/login"
                className="tr inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-display text-sm font-semibold text-primary-fg hover:opacity-90 active:scale-[0.98]"
              >
                Start intake
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="ml-0.5">
                  <path d="M1 7h12m0 0L8 2m5 5L8 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </Link>
              <span className="text-sm text-text-dim">3 steps · ~5 min</span>
            </div>
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-center gap-4 border-t border-border px-6 py-12 sm:px-10 lg:max-w-lg lg:border-l lg:border-t-0 lg:px-12 xl:max-w-xl xl:px-16">
          {FEATURES.map((f, i) => (
            <div
              key={f.num}
              className="anim-slide-right card-hover rounded-xl border border-border bg-surface p-5 sm:p-6"
              style={{ animationDelay: `${(i + 2) * 100}ms` }}
            >
              <div className="flex items-center gap-3">
                <span className={`font-mono text-xs font-medium ${f.accent}`}>{f.num}</span>
                <h3 className="font-display text-base font-semibold text-text">{f.title}</h3>
              </div>
              <p className="mt-2.5 text-sm leading-relaxed text-text-secondary">{f.desc}</p>
            </div>
          ))}
        </div>
      </main>

      <footer className="flex items-center justify-between border-t border-border px-6 py-3 sm:px-10">
        <span className="text-xs text-text-dim">Built for Hack-Nation Challenge</span>
        <span className="text-xs text-text-dim">2026</span>
      </footer>
    </div>
  );
}

function DashboardContent() {
  const [entries, setEntries] = useState<SpecListEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSpecsWithProgress()
      .then((e) => !cancelled && setEntries(e))
      .catch(() => !cancelled && setError("Could not load your specs. Check the backend and refresh."));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-bg ambient-glow">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <span className="font-display text-sm font-semibold tracking-tight text-text">
          PropertyRentalNegotiator
        </span>
        <div className="flex items-center gap-4">
          <span className="font-mono text-xs text-text-dim">Hack-Nation · 01</span>
          <NavAuth />
        </div>
      </nav>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-10 sm:px-10 lg:py-14">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs tracking-wider text-text-dim">Dashboard</p>
            <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
              Your specs
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
          <p className="rec-pulse py-12 text-center text-sm text-text-dim">Loading your specs...</p>
        )}
        {entries && entries.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 py-24 text-center">
            <p className="text-sm text-text-secondary">No specs yet — start your first shop rental search.</p>
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
      </main>
    </div>
  );
}
