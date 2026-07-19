"use client";

import Button from "@/components/ui/Button";
import StateBadge from "./StateBadge";
import { PERSONA_HINTS } from "@/lib/mocks";
import { PERSONAS, type Dealer, type DealerStatus, type Persona } from "@/lib/types";
import type { DealerCallState } from "@/lib/useCallCenter";

interface DealerCardProps {
  dealer: Dealer;
  callState: DealerCallState;
  selected: boolean;
  roleplay: boolean;
  onSelect: () => void;
  onCall: () => void;
  onPersonaChange: (persona: Persona) => void;
  onRoleplayChange: (on: boolean) => void;
  onStatusChange: (status: DealerStatus) => void;
}

export default function DealerCard({
  dealer,
  callState,
  selected,
  roleplay,
  onSelect,
  onCall,
  onPersonaChange,
  onRoleplayChange,
  onStatusChange,
}: DealerCardProps) {
  const { state, outcome, quotes } = callState;
  const busy = state === "calling" || state === "live";
  // "human" has no ElevenLabs agent — bridge calls need a persona assigned first.
  // Roleplay doesn't need one: a human is on the line either way.
  const noBridgeAgent = !roleplay && dealer.persona === "human";
  const declined = dealer.status === "declined";

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
            <span className="text-text-secondary">Ended: {outcome ?? "callback"}</span>
          )}
        </p>
      )}
      {state === "failed" && callState.error && (
        <p className="mt-2 text-xs text-error">{callState.error}</p>
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
