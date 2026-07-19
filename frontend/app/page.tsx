import Link from "next/link";
import NavAuth from "@/components/auth/NavAuth";

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
  return (
    <div className="flex min-h-screen flex-col bg-bg ambient-glow">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <Link
          href="/"
          className="tr font-display text-sm font-semibold tracking-tight text-text hover:text-accent"
        >
          PropertyRentalNegotiator
        </Link>
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

            <div className="anim-fade-up delay-225 mt-10 flex flex-wrap items-center gap-4">
              <Link
                href="/intake"
                className="tr inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-display text-sm font-semibold text-primary-fg hover:opacity-90 active:scale-[0.98]"
              >
                Start intake
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="ml-0.5">
                  <path d="M1 7h12m0 0L8 2m5 5L8 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </Link>
              <Link
                href="/dashboard"
                className="tr rounded-lg border border-border bg-surface px-6 py-3 font-display text-sm font-semibold text-text hover:border-border-hover hover:bg-elevated active:scale-[0.98]"
              >
                Go to your rental searches
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
