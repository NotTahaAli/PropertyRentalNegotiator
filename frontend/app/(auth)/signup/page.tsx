"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
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
    if (!loading && user) router.replace("/intake");
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
    router.replace("/intake");
  }

  if (needsConfirmation) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6 sm:p-8 text-center">
        <h1 className="font-display text-2xl font-bold tracking-tight text-text">
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
    <div className="rounded-xl border border-border bg-surface p-6 sm:p-8">
      <h1 className="font-display text-2xl font-bold tracking-tight text-text">
        Sign up
      </h1>
      <p className="mt-1.5 text-sm text-text-secondary">
        Your specs and calls stay private to your account.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
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
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
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
          {submitting ? "Creating account..." : "Create account"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-text-secondary">
        Have an account?{" "}
        <Link href="/login" className="tr text-accent hover:opacity-80">
          Log in
        </Link>
      </p>
    </div>
  );
}
