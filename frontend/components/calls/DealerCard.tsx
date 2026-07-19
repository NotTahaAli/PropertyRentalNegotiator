"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import StateBadge from "./StateBadge";
import TranscriptStream from "./TranscriptStream";
import { PERSONA_HINTS } from "@/lib/mocks";
import { OUTCOME_COPY, PERSONAS, type CallRow, type Dealer, type DealerStatus, type Persona } from "@/lib/types";
import type { DealerCallState } from "@/lib/useCallCenter";

interface DealerCardProps {
  dealer: Dealer;
  callState: DealerCallState;
  history: CallRow[];
  selected: boolean;
  roleplay: boolean;
  onSelect: () => void;
  onCall: () => void;
  onPersonaChange: (persona: Persona) => void;
  onRoleplayChange: (on: boolean) => void;
  onStatusChange: (status: DealerStatus) => void;
  // Deep-linked from a report citation: expand this round's transcript and
  // scroll/highlight the cited line.
  autoExpandCallId?: string;
  highlightLine?: number;
}

export default function DealerCard({
  dealer,
  callState,
  history,
  selected,
  roleplay,
  onSelect,
  onCall,
  onPersonaChange,
  onRoleplayChange,
  onStatusChange,
  autoExpandCallId,
  highlightLine,
}: DealerCardProps) {
  const { state, outcome, quotes } = callState;
  const busy = state === "calling" || state === "live";
  // "human" has no ElevenLabs agent — bridge calls need a persona assigned first.
  // Roleplay doesn't need one: a human is on the line either way.
  const noBridgeAgent = !roleplay && dealer.persona === "human";
  const declined = dealer.status === "declined";
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  // React's sanctioned prev-state pattern (see CallStatusPanel's linesCallId):
  // sync expandedCallId to a new deep-linked call during render, not an effect.
  const [syncedAutoExpand, setSyncedAutoExpand] = useState(autoExpandCallId);
  if (autoExpandCallId !== syncedAutoExpand) {
    setSyncedAutoExpand(autoExpandCallId);
    if (autoExpandCallId) setExpandedCallId(autoExpandCallId);
  }

  return (
    <div
      onClick={onSelect}
      className={`tr cursor-pointer rounded-xl border bg-surface p-4 ${
        selected ? "border-accent/50" : "border-border hover:border-border-hover"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-semibold text-text">
            {dealer.name}
            {dealer.source === "tavily" && (
              <span className="ml-2 rounded bg-elevated px-1.5 py-0.5 font-mono text-[9px] font-normal tracking-wider text-text-dim">
                DISCOVERED
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            {PERSONA_HINTS[dealer.persona]}
          </p>
          {dealer.phone_label && (
            <p className="mt-1 font-mono text-[10px] text-text-dim">{dealer.phone_label}</p>
          )}
          {(dealer.phone || dealer.rating != null) && (
            <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-text-dim">
              {dealer.phone && <span>{dealer.phone}</span>}
              {dealer.rating != null && (
                <span title={dealer.rating_source ? `Source: ${dealer.rating_source}` : undefined}>
                  ★ {dealer.rating.toFixed(1)}
                </span>
              )}
            </p>
          )}
          <label
            className="mt-2 flex items-center gap-2 text-[11px] text-text-secondary"
            onClick={(e) => e.stopPropagation()}
          >
            Persona
            <select
              value={dealer.persona}
              disabled={busy}
              onChange={(e) => onPersonaChange(e.target.value as Persona)}
              className="rounded border border-border bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-text"
            >
              {PERSONAS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>
        <StateBadge state={state} />
      </div>

      {/* done summary line */}
      {state === "done" && (
        <p className="mt-2 text-xs">
          {outcome === "quote" && quotes.length > 0 ? (
            <span className="text-success">
              {quotes.length === 1
                ? `Quoted PKR ${new Intl.NumberFormat("en-PK").format(quotes[0].total_first_year)} first year`
                : `${quotes.length} quotes — cheapest PKR ${new Intl.NumberFormat("en-PK").format(
                    Math.min(...quotes.map((q) => q.total_first_year))
                  )} first year`}
              {quotes.some((q) => q.flagged) && (
                <span
                  className="ml-2 rounded-md bg-error-dim px-2 py-0.5 font-mono text-[10px] text-error"
                  title={quotes.find((q) => q.flagged)?.flag_reason ?? undefined}
                >
                  flagged
                </span>
              )}
            </span>
          ) : outcome === "declined" ? (
            <span className="text-error">Declined — unit not available</span>
          ) : (
            <span className="text-text-secondary">
              {outcome ? OUTCOME_COPY[outcome].label : "Call ended — outcome not recorded yet"}
            </span>
          )}
        </p>
      )}
      {state === "failed" && callState.error && (
        <p className="mt-2 text-xs text-error">{callState.error}</p>
      )}

      {/* every past call to this dealer, all rounds — client can read any of them */}
      {history.length > 0 && (
        <div className="mt-3 border-t border-border pt-2" onClick={(e) => e.stopPropagation()}>
          <p className="font-mono text-[10px] uppercase tracking-wide text-text-dim">
            Call history
          </p>
          <div className="mt-1.5 flex flex-col gap-1">
            {history.map((c) => (
              <div key={c.id}>
                <button
                  type="button"
                  onClick={() => setExpandedCallId(expandedCallId === c.id ? null : c.id)}
                  className="flex w-full items-center justify-between gap-2 rounded px-1.5 py-1 text-left text-[11px] text-text-secondary hover:bg-elevated"
                >
                  <span>
                    Round {c.round}
                    {c.status === "failed"
                      ? " — failed"
                      : c.outcome
                        ? ` — ${OUTCOME_COPY[c.outcome].label}`
                        : c.status === "running"
                          ? " — in progress"
                          : ""}
                  </span>
                  <span className="font-mono text-text-dim">
                    {c.started_at ? new Date(c.started_at).toLocaleString() : ""}
                  </span>
                </button>
                {expandedCallId === c.id && (
                  <div className="mt-1 rounded-lg border border-border bg-elevated p-2">
                    <TranscriptStream
                      lines={c.transcript_json ?? []}
                      highlightLine={autoExpandCallId === c.id ? highlightLine : undefined}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-3">
        {declined ? (
          <>
            <p className="font-mono text-[11px] uppercase tracking-wide text-error">
              Declined
            </p>
            <Button
              variant="secondary"
              className="px-4 py-1.5 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                onStatusChange("active");
              }}
            >
              Reactivate
            </Button>
          </>
        ) : (
          <>
            <Button
              variant={state === "done" ? "secondary" : "primary"}
              className="px-4 py-1.5 text-xs"
              disabled={busy || noBridgeAgent}
              title={noBridgeAgent ? "Assign a persona to bridge-call, or answer as dealer" : undefined}
              onClick={(e) => {
                e.stopPropagation();
                onCall();
              }}
            >
              {state === "failed"
                ? "Retry call"
                : state === "done"
                  ? `Round ${(callState.round ?? 1) + 1}${roleplay ? " roleplay" : ""} call`
                  : roleplay
                    ? "Start roleplay call"
                    : "Call"}
            </Button>

            <div className="flex items-center gap-3">
              {/* role-play mode toggle — primary demo path, not a fallback */}
              <label
                className="flex cursor-pointer items-center gap-2 text-xs text-text-secondary"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  checked={roleplay}
                  disabled={busy}
                  onChange={(e) => onRoleplayChange(e.target.checked)}
                  className="accent-[#CFA44E]"
                />
                Answer as dealer
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation();
                  onStatusChange("declined");
                }}
                className="text-[11px] text-text-dim hover:text-error disabled:opacity-50"
              >
                Decline
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
