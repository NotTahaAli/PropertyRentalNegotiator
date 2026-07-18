"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import PasswordInput from "@/components/ui/PasswordInput";
import { useAuth } from "@/components/auth/AuthProvider";

export default function SignupPage() {
  const router = useRouter();
  const { user, loading, signUp } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await signUp(email, password);
    setSubmitting(false);
    if (res.error) {
      setError(res.error);
      return;
    }
    if (res.needsConfirmation) {
      setNeedsConfirmation(true);
      return;
    }
    router.replace("/");
  }

  if (needsConfirmation) {
    return (
      <div className="anim-scale-in rounded-xl border border-border bg-surface p-6 text-center sm:p-8">
        <div className="mx-auto inline-flex rounded-full border border-success/20 bg-success/10 p-3 text-success">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M3 6l7 5 7-5M3 5.5A1.5 1.5 0 014.5 4h11A1.5 1.5 0 0117 5.5v9a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 013 14.5v-9z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="mt-4 font-display text-2xl font-bold tracking-tight text-text">
          Check your email
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary">
          We sent a confirmation link to{" "}
          <span className="font-mono text-text">{email}</span>. Confirm it, then
          log in.
        </p>
        <Link
          href="/login"
          className="tr mt-6 inline-block text-sm text-accent hover:opacity-80"
        >
          Go to login →
        </Link>
      </div>
    );
  }

  return (
    <div>
      <p className="anim-fade-up font-mono text-xs tracking-wider text-text-dim">
        Get started
      </p>
      <h1 className="anim-fade-up delay-75 mt-3 font-display text-3xl font-bold tracking-tight text-text sm:text-4xl">
        Create your account<span className="text-accent">.</span>
      </h1>
      <p className="anim-fade-up delay-150 mt-2 text-sm text-text-secondary">
        Your specs and calls stay private to your account.
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
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="mt-1.5 text-xs text-text-dim">At least 6 characters.</p>
        </div>

        {error && (
          <p role="alert" className="rounded-lg bg-error-dim px-3.5 py-2.5 text-sm text-error">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting} className="mt-1 w-full">
          {submitting ? "Creating account..." : "Create account"}
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
        Have an account?{" "}
        <Link href="/login" className="tr text-accent hover:opacity-80">
          Log in
        </Link>
      </p>
    </div>
  );
}
