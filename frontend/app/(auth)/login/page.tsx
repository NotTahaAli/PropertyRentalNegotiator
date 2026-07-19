"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import PasswordInput from "@/components/ui/PasswordInput";
import { useAuth } from "@/components/auth/AuthProvider";

function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") ? next : "/dashboard";
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace(nextPath());
  }, [loading, user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const err = await signIn(email, password);
    setSubmitting(false);
    if (err) {
      setError(err);
      return;
    }
    router.replace(nextPath());
  }

  return (
    <div>
      <p className="anim-fade-up font-mono text-xs tracking-wider text-text-dim">
        Welcome back
      </p>
      <h1 className="anim-fade-up delay-75 mt-3 font-display text-3xl font-bold tracking-tight text-text sm:text-4xl">
        Log in<span className="text-accent">.</span>
      </h1>
      <p className="anim-fade-up delay-150 mt-2 text-sm text-text-secondary">
        Pick up where you left off.
      </p>

      <form
        onSubmit={handleSubmit}
        className="anim-fade-up delay-225 mt-8 flex flex-col gap-4 rounded-xl border border-border bg-surface p-6 sm:p-7"
      >
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-text">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-text">
            Password
          </label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && (
          <p role="alert" className="rounded-lg bg-error-dim px-3.5 py-2.5 text-sm text-error">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting} className="mt-1 w-full">
          {submitting ? "Logging in..." : "Log in"}
          {!submitting && (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path
                d="M1 7h12m0 0L8 2m5 5L8 12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </Button>
      </form>

      <p className="anim-fade-up delay-300 mt-5 text-center text-sm text-text-secondary">
        No account?{" "}
        <Link href="/signup" className="tr text-accent hover:opacity-80">
          Sign up
        </Link>
      </p>
    </div>
  );
}
