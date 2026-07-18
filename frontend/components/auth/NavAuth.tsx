"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";
import AccountChip from "./AccountChip";

export default function NavAuth() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (user) return <AccountChip />;

  return (
    <Link
      href="/login"
      className="tr rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-elevated hover:text-text"
    >
      Log in
    </Link>
  );
}
