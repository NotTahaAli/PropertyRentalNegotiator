"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export default function AccountChip() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  if (!user) return null;

  return (
    <div className="flex items-center gap-3">
      <span className="hidden font-mono text-xs text-text-dim sm:inline">
        {user.email}
      </span>
      <button
        type="button"
        onClick={async () => {
          await signOut();
          router.replace("/login");
        }}
        className="tr rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-elevated hover:text-text"
      >
        Sign out
      </button>
    </div>
  );
}
