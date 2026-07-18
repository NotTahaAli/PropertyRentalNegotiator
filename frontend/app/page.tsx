import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-ink text-center">
      <h1 className="font-display text-4xl text-text">The Negotiator</h1>
      <p className="mt-3 max-w-md text-muted">
        Voice agents call Pakistani property dealers, extract itemised rent
        quotes, and rank them for you.
      </p>
      <Link
        href="/intake"
        className="mt-8 rounded-full bg-amber px-6 py-3 font-mono text-sm uppercase tracking-wide text-ink"
      >
        Start Intake
      </Link>
    </div>
  );
}
