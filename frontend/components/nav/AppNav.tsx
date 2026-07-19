import Link from "next/link";
import AccountChip from "@/components/auth/AccountChip";

export interface Crumb {
  label: string;
  href?: string; // omit for the current (terminal) page — rendered as plain text
}

// same header-scale button pattern already used by AccountChip's sign-out
// button and NavAuth's log-in link — reused here, not a new style.
const NAV_LINK_CLASS =
  "tr shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-elevated hover:text-text";

// Shared nav bar for every authenticated app layout (dashboard/calls/report/
// intake) — logo always returns to the public landing page; persistent
// Specs/New spec links go to their pages (these pages are all Protected, so
// a user is always logged in here); an optional breadcrumb adds
// page-specific context (which spec, which section) after them.
export default function AppNav({ crumbs = [], className = "" }: { crumbs?: Crumb[]; className?: string }) {
  return (
    <nav
      className={`flex items-center justify-between gap-4 border-b border-border px-6 py-4 sm:px-10 ${className}`}
    >
      <div className="flex min-w-0 items-center gap-1 sm:gap-3">
        <Link
          href="/"
          className="tr mr-1 shrink-0 font-display text-sm font-semibold tracking-tight text-text hover:text-accent sm:mr-3"
        >
          PropertyRentalNegotiator
        </Link>
        <Link href="/dashboard" className={NAV_LINK_CLASS}>
          Specs
        </Link>
        <Link href="/intake" className={NAV_LINK_CLASS}>
          New spec
        </Link>
        {crumbs.length > 0 && (
          <div className="flex min-w-0 items-center gap-1.5 font-mono text-xs text-text-dim">
            <span aria-hidden="true">/</span>
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
        )}
      </div>
      <AccountChip />
    </nav>
  );
}
