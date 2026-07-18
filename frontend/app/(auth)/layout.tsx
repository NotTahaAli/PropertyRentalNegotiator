import Link from "next/link";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-bg ambient-glow">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <Link
          href="/"
          className="tr font-display text-sm font-semibold tracking-tight text-text hover:text-accent"
        >
          PropertyRentalNegotiator
        </Link>
        <span className="font-mono text-xs text-text-dim">Account</span>
      </nav>
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
