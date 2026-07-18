import OnAirDot from "@/components/ui/OnAirDot";

export default function IntakeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-ink text-text">
      <header className="border-b border-line px-7 py-6">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <OnAirDot />
          <span className="font-mono text-[11px] uppercase tracking-[.18em] text-amber">
            The Negotiator · Intake
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-7 py-10">{children}</main>
    </div>
  );
}
