"use client";

import { useParams } from "next/navigation";
import Button from "@/components/ui/Button";
import DealerCard from "@/components/calls/DealerCard";
import CallStatusPanel from "@/components/calls/CallStatusPanel";
import { useCallCenter } from "@/lib/useCallCenter";

export default function CallCenterPage() {
  const params = useParams<{ spec_id: string }>();
  const specId = params.spec_id;
  const { dealers, dealersError, selected, select, call, callAll, stateFor } =
    useCallCenter(specId);

  const anyIdle = dealers?.some((d) => {
    const s = stateFor(d.id).state;
    return s === "idle" || s === "failed";
  });

  const selectedDealer = dealers?.find((d) => d.id === selected) ?? null;

  return (
    <div className="anim-fade-up flex flex-1 flex-col">
      {/* header */}
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-wider text-text-dim">
            Spec {specId}
          </p>
          <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
            Call center
          </h2>
          <p className="mt-1.5 max-w-lg text-sm text-text-secondary">
            The Negotiator calls each dealer for an itemised quote. Watch the
            calls live; quotes land here as they are logged.
          </p>
        </div>
        <Button onClick={callAll} disabled={!dealers || !anyIdle}>
          Call all dealers
        </Button>
      </div>

      {/* states */}
      {dealersError && (
        <p role="alert" className="rounded-lg bg-error-dim px-4 py-3 text-sm text-error">
          {dealersError} Check the backend and refresh.
        </p>
      )}
      {!dealers && !dealersError && (
        <p className="rec-pulse py-12 text-center text-sm text-text-dim">
          Loading dealers...
        </p>
      )}
      {dealers && dealers.length === 0 && (
        <p className="rounded-lg border border-dashed border-border-hover bg-surface px-4 py-6 text-sm text-text-secondary">
          No dealers on this spec yet. Dealer seeding per spec is an open
          backend decision — see STATUS.md.
        </p>
      )}

      {/* main grid */}
      {dealers && dealers.length > 0 && (
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="flex flex-col gap-3 lg:w-[38%]">
            {dealers.map((d) => (
              <DealerCard
                key={d.id}
                dealer={d}
                callState={stateFor(d.id)}
                selected={selected === d.id}
                onSelect={() => select(d.id)}
                onCall={() => call(d.id)}
              />
            ))}
          </div>
          <div className="flex-1 lg:sticky lg:top-8 lg:self-start">
            <CallStatusPanel
              dealer={selectedDealer}
              callState={selectedDealer ? stateFor(selectedDealer.id) : { state: "idle", transcript: [] }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
