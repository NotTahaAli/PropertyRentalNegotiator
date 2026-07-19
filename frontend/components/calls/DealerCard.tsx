"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import StateBadge from "./StateBadge";
import { PERSONA_HINTS } from "@/lib/mocks";
import { PERSONAS, type Dealer, type Persona } from "@/lib/types";
import type { DealerCallState } from "@/lib/useCallCenter";

interface DealerCardProps {
  dealer: Dealer;
  callState: DealerCallState;
  selected: boolean;
  onSelect: () => void;
  onCall: () => void;
  onPersonaChange: (persona: Persona) => void;
}

export default function DealerCard({
  dealer,
  callState,
  selected,
  onSelect,
  onCall,
  onPersonaChange,
}: DealerCardProps) {
  const [roleplay, setRoleplay] = useState(false);
  const { state, outcome, quote } = callState;
  const busy = state === "calling" || state === "live";
  // "human" has no ElevenLabs agent — bridge calls need a persona assigned first
  const noBridgeAgent = dealer.persona === "human";

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
          {outcome === "quote" && quote ? (
            <span className="text-success">
              Quoted PKR {new Intl.NumberFormat("en-PK").format(quote.total_first_year)} first year
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
        <Button
          variant={state === "done" ? "secondary" : "primary"}
          className="px-4 py-1.5 text-xs"
          disabled={busy || roleplay || noBridgeAgent}
          title={noBridgeAgent ? "Assign a persona to bridge-call, or use role-play" : undefined}
          onClick={(e) => {
            e.stopPropagation();
            onCall();
          }}
        >
          {state === "failed" ? "Retry call" : state === "done" ? "Call again" : "Call"}
        </Button>

        {/* role-play mode toggle — K5-fallback demo path */}
        <label
          className="flex cursor-pointer items-center gap-2 text-xs text-text-secondary"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={roleplay}
            onChange={(e) => setRoleplay(e.target.checked)}
            className="accent-[#CFA44E]"
          />
          Answer as dealer
        </label>
      </div>

      {roleplay && (
        <div className="mt-3 rounded-lg border border-dashed border-border-hover bg-elevated p-3">
          <p className="text-xs text-text-dim">
            Role-play mode: the ElevenLabs widget embeds here with the negotiator
            agent — you answer as {dealer.name}. Blocked on B confirming the
            widget dynamic-variables wiring (see STATUS.md).
          </p>
        </div>
      )}
    </div>
  );
}
