"use client";

import { useEffect, useState } from "react";
import AudioPlayer from "./AudioPlayer";
import CharacterCard from "./CharacterCard";
import LiveAudio from "./LiveAudio";
import RoleplaySession from "./RoleplaySession";
import StateBadge from "./StateBadge";
import TranscriptStream from "./TranscriptStream";
import type { Dealer, TranscriptLine } from "@/lib/types";
import type { DealerCallState } from "@/lib/useCallCenter";

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

  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {formatElapsed(elapsed)}
    </span>
  );
}

const OUTCOME_LABELS: Record<string, { text: string; className: string }> = {
  declined: { text: "Dealer declined — unit not available", className: "bg-error-dim text-error" },
  callback: { text: "Dealer asked for a callback — no numbers committed", className: "bg-elevated text-text-secondary" },
  failed: { text: "Call failed before completing", className: "bg-error-dim text-error" },
  // Shown when the backend never recorded an outcome (call not finalized, or the
  // post-call webhook never landed). Saying "no numbers committed" here would be
  // asserting something we don't know.
  unrecorded: {
    text: "Call ended — outcome not recorded yet",
    className: "bg-elevated text-text-secondary",
  },
};

interface CallStatusPanelProps {
  dealer: Dealer | null;
  callState: DealerCallState;
  roleplay: boolean;
  onRoleplaySessionEnded: () => void;
  onHangUp: () => void;
  highlightLine?: number;
}

export default function CallStatusPanel({
  dealer,
  callState,
  roleplay,
  onRoleplaySessionEnded,
  onHangUp,
  highlightLine,
}: CallStatusPanelProps) {
  // live transcript lines from the bridge stream; the authoritative
  // transcript_json (numbered, deduped) replaces them once the call completes
  const [liveLines, setLiveLines] = useState<TranscriptLine[]>([]);
  const [linesCallId, setLinesCallId] = useState(callState.callId);
  if (callState.callId !== linesCallId) {
    // new call: reset during render (React's sanctioned prev-state pattern)
    setLinesCallId(callState.callId);
    setLiveLines([]);
  }

  if (!dealer) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <p className="text-sm text-text-dim">Select a dealer to see the call.</p>
      </div>
    );
  }

  const { state, transcript, outcome, quotes, recordingUrl, error, negotiatorAgentId, dynamicVariables } =
    callState;

  // roleplay session in progress: character card + voice controls, side by side.
  // Once the call reaches done/failed it falls through to the normal render below
  // (same transcript/quote/audio path bridge mode uses).
  if (roleplay && (state === "idle" || state === "calling" || state === "live")) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
          <p className="truncate font-display text-base font-semibold text-text">{dealer.name}</p>
          <StateBadge state={state} />
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <CharacterCard dealer={dealer} />
          <div>
            {state === "idle" && (
              <p className="rounded-xl border border-dashed border-border-hover bg-elevated p-5 text-sm text-text-dim">
                Read the character card, then hit &quot;Start roleplay call&quot;
                on the dealer&apos;s card to begin.
              </p>
            )}
            {state === "calling" && (
              <p className="rec-pulse rounded-xl border border-border bg-elevated p-5 text-sm text-text-secondary">
                Starting roleplay call...
              </p>
            )}
            {state === "live" && (
              <RoleplaySession
                agentId={negotiatorAgentId}
                dynamicVariables={dynamicVariables}
                onEnded={onRoleplaySessionEnded}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

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
          {state === "live" && (
            <button
              onClick={onHangUp}
              className="rounded-lg bg-error-dim px-3 py-1.5 text-xs font-medium text-error transition-colors hover:bg-error hover:text-white"
            >
              End call
            </button>
          )}
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
        {state === "live" && callState.mode === "bridge" && callState.callId && (
          <LiveAudio
            callId={callState.callId}
            onLine={(leg, text) =>
              setLiveLines((prev) => [...prev, { line: prev.length + 1, speaker: leg, text }])
            }
          />
        )}
        {(state === "live" || state === "done" || state === "failed") && (
          <TranscriptStream
            lines={transcript.length > 0 ? transcript : liveLines}
            highlightLine={highlightLine}
          />
        )}
      </div>

      {/* completed extras — the quote itself lives in the page's quote panel */}
      {state === "done" && (
        <div className="mt-5 flex flex-col gap-4 border-t border-border pt-4">
          {!(outcome === "quote" && quotes.length > 0) && (
            <div
              className={`rounded-lg px-3.5 py-2.5 text-sm ${
                (OUTCOME_LABELS[outcome ?? "unrecorded"] ?? OUTCOME_LABELS.unrecorded).className
              }`}
            >
              {(OUTCOME_LABELS[outcome ?? "unrecorded"] ?? OUTCOME_LABELS.unrecorded).text}
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
