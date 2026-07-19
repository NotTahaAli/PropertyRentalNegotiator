"use client";

import { useEffect, useState } from "react";
import AudioPlayer from "./AudioPlayer";
import QuoteChip from "./QuoteChip";
import StateBadge from "./StateBadge";
import TranscriptStream from "./TranscriptStream";
import type { Dealer } from "@/lib/types";
import type { DealerCallState } from "@/lib/useCallCenter";

const MAX_CALL_SECONDS = 180; // backend bridge hard cap

function formatElapsed(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

function ElapsedTicker({ startedAt, live }: { startedAt?: number; live: boolean }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [live]);

  if (!startedAt) return null;
  const elapsed = Math.floor((now - startedAt) / 1000);
  const capped = Math.min(elapsed, MAX_CALL_SECONDS);
  const stale = live && elapsed > MAX_CALL_SECONDS;

  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {formatElapsed(capped)}
      {stale && (
        <span className="ml-2 text-error">call timed out? backend caps at 3:00</span>
      )}
    </span>
  );
}

const OUTCOME_LABELS: Record<string, { text: string; className: string }> = {
  declined: { text: "Dealer declined — unit not available", className: "bg-error-dim text-error" },
  callback: { text: "Dealer asked for a callback — no numbers committed", className: "bg-elevated text-text-secondary" },
  failed: { text: "Call failed before completing", className: "bg-error-dim text-error" },
};

interface CallStatusPanelProps {
  dealer: Dealer | null;
  callState: DealerCallState;
}

export default function CallStatusPanel({ dealer, callState }: CallStatusPanelProps) {
  if (!dealer) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <p className="text-sm text-text-dim">Select a dealer to see the call.</p>
      </div>
    );
  }

  const { state, transcript, outcome, quote, recordingUrl, error } = callState;

  return (
    <div className="rounded-xl border border-border bg-surface p-5 sm:p-6">
      {/* header */}
      <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
        <div className="min-w-0">
          <p className="truncate font-display text-base font-semibold text-text">
            {dealer.name}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ElapsedTicker startedAt={callState.startedAt} live={state === "live"} />
          <StateBadge state={state} />
        </div>
      </div>

      {/* soft error (transient poll failures) */}
      {error && state !== "failed" && (
        <p className="mt-3 rounded-lg bg-error-dim px-3 py-2 text-xs text-error">{error}</p>
      )}

      {/* body */}
      <div className="mt-4">
        {state === "idle" && (
          <p className="py-6 text-center text-sm text-text-dim">
            No call yet. Hit Call to start the negotiation.
          </p>
        )}
        {state === "calling" && (
          <p className="rec-pulse py-6 text-center text-sm text-text-secondary">
            Dialing {dealer.name}...
          </p>
        )}
        {(state === "live" || state === "done" || state === "failed") && (
          <TranscriptStream lines={transcript} />
        )}
      </div>

      {/* completed extras */}
      {state === "done" && (
        <div className="mt-5 flex flex-col gap-4 border-t border-border pt-4">
          {outcome === "quote" && quote ? (
            <QuoteChip quote={quote} />
          ) : (
            <div
              className={`rounded-lg px-3.5 py-2.5 text-sm ${
                (OUTCOME_LABELS[outcome ?? "callback"] ?? OUTCOME_LABELS.callback).className
              }`}
            >
              {(OUTCOME_LABELS[outcome ?? "callback"] ?? OUTCOME_LABELS.callback).text}
            </div>
          )}
          <AudioPlayer url={recordingUrl} />
        </div>
      )}
      {state === "failed" && error && (
        <p className="mt-4 rounded-lg bg-error-dim px-3.5 py-2.5 text-sm text-error">{error}</p>
      )}
    </div>
  );
}
