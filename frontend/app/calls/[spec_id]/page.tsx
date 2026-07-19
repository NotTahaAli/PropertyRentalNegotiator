"use client";

import { useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Button from "@/components/ui/Button";
import DealerCard from "@/components/calls/DealerCard";
import CallStatusPanel from "@/components/calls/CallStatusPanel";
import { MOCK_DEALERS, MOCK_REPORT } from "@/lib/mocks";
import { useCallCenter } from "@/lib/useCallCenter";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

export default function CallCenterPage() {
  const params = useParams<{ spec_id: string }>();
  const specId = params.spec_id;
  const searchParams = useSearchParams();
  const router = useRouter();
  const {
    dealers,
    dealersError,
    selected,
    select,
    call,
    callAll,
    hangUp,
    setPersona,
    roleplay,
    setRoleplay,
    finishRoleplaySession,
    seedMockCompleted,
    stateFor,
  } = useCallCenter(specId);

  // Report citation deep-link: ?call=<1-based dealer index>&line=<n>. Seeding
  // a canned completed call only ever happens under USE_MOCKS — in real mode
  // this just selects the dealer (if resolvable) and highlights the line if
  // it's already in whatever transcript is really there; it never invents one.
  const callParam = searchParams.get("call");
  const lineParam = searchParams.get("line");
  const highlightLine = lineParam ? Number(lineParam) : undefined;

  useEffect(() => {
    if (!USE_MOCKS || !callParam || !dealers) return;
    const dealer = MOCK_DEALERS[Number(callParam) - 1];
    if (!dealer) return;
    select(dealer.id);
    if (stateFor(dealer.id).state === "idle") {
      const row = MOCK_REPORT.rows.find((r) => r.dealer_id === dealer.id);
      seedMockCompleted(dealer.id, row?.round ?? 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callParam, dealers]);

  const anyIdle = dealers?.some((d) => {
    const s = stateFor(d.id).state;
    return s === "idle" || s === "failed";
  });
  // terminal = done or failed; "calling"/"live" mean this round isn't over yet
  const allTerminal =
    !!dealers && dealers.length > 0 && dealers.every((d) => {
      const s = stateFor(d.id).state;
      return s === "done" || s === "failed";
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
        <div className="flex items-center gap-3">
          <Button onClick={callAll} disabled={!dealers || !anyIdle}>
            Call all dealers
          </Button>
          <Button
            variant="secondary"
            disabled={!allTerminal}
            title={allTerminal ? undefined : "Every dealer needs a done/declined/failed call first"}
            onClick={() => router.push(`/report/${encodeURIComponent(specId)}`)}
          >
            View report
          </Button>
        </div>
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
                roleplay={!!roleplay[d.id]}
                onSelect={() => select(d.id)}
                onCall={() => call(d.id)}
                onPersonaChange={(p) => void setPersona(d.id, p)}
                onRoleplayChange={(on) => setRoleplay(d.id, on)}
              />
            ))}
          </div>
          <div className="flex-1 lg:sticky lg:top-8 lg:self-start">
            <CallStatusPanel
              dealer={selectedDealer}
              callState={selectedDealer ? stateFor(selectedDealer.id) : { state: "idle", transcript: [] }}
              roleplay={selectedDealer ? !!roleplay[selectedDealer.id] : false}
              onRoleplaySessionEnded={() => selectedDealer && finishRoleplaySession(selectedDealer.id)}
              onHangUp={() => selectedDealer && hangUp(selectedDealer.id)}
              highlightLine={highlightLine}
            />
          </div>
        </div>
      )}
    </div>
  );
}
