import Link from "next/link";
import AccountChip from "@/components/auth/AccountChip";
import Protected from "@/components/auth/Protected";

export default function ReportLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text print:bg-white print:text-black">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10 print:hidden">
        <Link
          href="/"
          className="tr font-display text-sm font-semibold tracking-tight text-text hover:text-accent"
        >
          PropertyRentalNegotiator
        </Link>
        <div className="flex items-center gap-4">
          <span className="font-mono text-xs text-text-dim">Report</span>
          <AccountChip />
        </div>
      </nav>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6 py-8 sm:px-10 lg:py-12 print:max-w-none print:px-0">
        <Protected>{children}</Protected>
      </main>
    </div>
  );
}
