import Link from "next/link";

export default function IntakeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      {/* ── nav bar ── */}
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <Link
          href="/"
          className="tr font-display text-sm font-semibold tracking-tight text-text hover:text-accent"
        >
          PropertyRentalNegotiator
        </Link>
        <span className="font-mono text-xs text-text-dim">
          Intake form
        </span>
      </nav>

      {/* ── content ── */}
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-8 sm:px-10 lg:py-12">
        {children}
      </main>
    </div>
  );
}
