import Link from "next/link";
import AccountChip from "@/components/auth/AccountChip";

export interface Crumb {
  label: string;
  href?: string; // omit for the current (terminal) page — rendered as plain text
}

// Shared nav bar for every authenticated app layout (dashboard/calls/report/
// intake) — logo always goes to /dashboard (these pages are all Protected,
// so a user is always logged in here), breadcrumb gives wayfinding back to
// the dashboard and, on calls/report, back to the spec.
export default function AppNav({ crumbs, className = "" }: { crumbs: Crumb[]; className?: string }) {
  return (
    <nav className={`flex items-center justify-between border-b border-border px-6 py-4 sm:px-10 ${className}`}>
      <Link
        href="/dashboard"
        className="tr font-display text-sm font-semibold tracking-tight text-text hover:text-accent"
      >
        PropertyRentalNegotiator
      </Link>
      <div className="flex items-center gap-4">
        <div className="flex min-w-0 items-center gap-1.5 font-mono text-xs text-text-dim">
          {crumbs.map((c, i) => (
            <span key={i} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && <span aria-hidden="true">/</span>}
              {c.href ? (
                <Link href={c.href} className="tr truncate hover:text-accent">
                  {c.label}
                </Link>
              ) : (
                <span className="truncate text-text-secondary">{c.label}</span>
              )}
            </span>
          ))}
        </div>
        <AccountChip />
      </div>
    </nav>
  );
}
