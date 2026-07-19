"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Button from "@/components/ui/Button";
import DealerCard from "@/components/calls/DealerCard";
import CallStatusPanel from "@/components/calls/CallStatusPanel";
import QuoteChip from "@/components/calls/QuoteChip";
import BenchmarkBadge from "@/components/spec/BenchmarkBadge";
import { MOCK_DEALERS, MOCK_REPORT } from "@/lib/mocks";
import { discoverMoreDealers, getSpec } from "@/lib/api";
import type { Benchmark } from "@/lib/types";
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
    followUp,
    callAll,
    hangUp,
    setPersona,
    setDealerStatus,
    roleplay,
    setRoleplay,
    finishRoleplaySession,
    seedMockCompleted,
    addDealers,
    stateFor,
    historyFor,
    resolveCallNumber,
  } = useCallCenter(specId);

  const [benchmark, setBenchmark] = useState<Benchmark | null | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    getSpec(specId)
      .then((s) => !cancelled && setBenchmark(s.benchmark_json ?? null))
      .catch(() => !cancelled && setBenchmark(null));
    return () => {
      cancelled = true;
    };
  }, [specId]);

  const [discovering, setDiscovering] = useState(false);
  const [discoverNote, setDiscoverNote] = useState<string | null>(null);
  async function searchMoreDealers() {
    setDiscovering(true);
    setDiscoverNote(null);
    try {
      const { added } = await discoverMoreDealers(specId);
      addDealers(added);
      setDiscoverNote(
        added.length === 0 ? "No new dealers found." : `Found ${added.length} new dealer${added.length === 1 ? "" : "s"}.`
      );
    } catch {
      setDiscoverNote("Could not search for more dealers.");
    } finally {
      setDiscovering(false);
    }
  }

  // Report citation deep-link: ?call=<call_number>&line=<n>. Mock mode seeds a
  // canned completed call; real mode resolves call_number against every call
  // fetched for this spec (same ordering as the backend's report citations)
  // and expands that specific round's transcript, even if it isn't the
  // dealer's latest round.
  const callParam = searchParams.get("call");
  const lineParam = searchParams.get("line");
  const highlightLine = lineParam ? Number(lineParam) : undefined;
  const [deepLinkCallId, setDeepLinkCallId] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!callParam || !dealers) return;
    // Deferred a tick: numberedCalls (real mode) hydrates asynchronously in
    // useCallCenter right after `dealers` is set, so resolving in the same
    // tick `dealers` arrives can race it. Matches the async-IIFE idiom
    // useCallCenter's own hydration effect uses for the same reason.
    void (async () => {
      if (USE_MOCKS) {
        const dealer = MOCK_DEALERS[Number(callParam) - 1];
        if (!dealer) return;
        select(dealer.id);
        if (stateFor(dealer.id).state === "idle") {
          const row = MOCK_REPORT.rows.find((r) => r.dealer_id === dealer.id);
          seedMockCompleted(dealer.id, row?.round ?? 1);
        }
        return;
      }
      const resolved = resolveCallNumber(Number(callParam));
      if (!resolved) return;
      select(resolved.dealer_id);
      setDeepLinkCallId(resolved.id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callParam, dealers, resolveCallNumber]);

  const anyIdle = dealers?.some((d) => {
    if (d.status === "declined") return false;
    const s = stateFor(d.id).state;
    return s === "idle" || s === "failed";
  });
  // terminal = done or failed, or manually declined even without a call yet;
  // "calling"/"live" mean this round isn't over yet
  const allTerminal =
    !!dealers && dealers.length > 0 && dealers.every((d) => {
      if (d.status === "declined") return true;
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
          <div className="mt-3">
            <BenchmarkBadge benchmark={benchmark} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end gap-1.5">
            <Button variant="secondary" onClick={searchMoreDealers} disabled={discovering}>
              {discovering ? "Searching..." : "Search more dealers"}
            </Button>
            {discoverNote && (
              <p className="text-xs text-text-dim" role="status">
                {discoverNote}
              </p>
            )}
          </div>
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
          <div className="flex flex-col gap-3 lg:w-[30%]">
            {dealers.map((d) => (
              <DealerCard
                key={d.id}
                dealer={d}
                callState={stateFor(d.id)}
                history={historyFor(d.id)}
                selected={selected === d.id}
                roleplay={!!roleplay[d.id]}
                onSelect={() => select(d.id)}
                onCall={() => call(d.id)}
                onPersonaChange={(p) => void setPersona(d.id, p)}
                onRoleplayChange={(on) => setRoleplay(d.id, on)}
                onStatusChange={(s) => void setDealerStatus(d.id, s)}
                autoExpandCallId={deepLinkCallId && d.id === selected ? deepLinkCallId : undefined}
                highlightLine={deepLinkCallId && d.id === selected ? highlightLine : undefined}
              />
            ))}
          </div>
          <div className="flex-1 lg:sticky lg:top-8 lg:self-start">
            <CallStatusPanel
              dealer={selectedDealer}
              callState={selectedDealer ? stateFor(selectedDealer.id) : { state: "idle", transcript: [], quotes: [] }}
              roleplay={selectedDealer ? !!roleplay[selectedDealer.id] : false}
              onRoleplaySessionEnded={() => selectedDealer && finishRoleplaySession(selectedDealer.id)}
              onHangUp={() => selectedDealer && hangUp(selectedDealer.id)}
              highlightLine={highlightLine}
            />
          </div>
          {/* live quote panel(s) — fills as soon as log_quote writes a row mid-call.
              A dealer with several matching properties gets one chip per quote. */}
          <div className="flex flex-col gap-3 lg:sticky lg:top-8 lg:w-[26%] lg:self-start">
            {(() => {
              const s = selectedDealer ? stateFor(selectedDealer.id) : null;
              if (s && s.quotes.length > 0) {
                // Rounds are unlimited; a follow-up just isn't offered while a
                // call is in flight or the dealer has been declined.
                const canFollowUp = s.state === "done" && selectedDealer?.status !== "declined";
                return s.quotes.map((q, i) => (
                  <div key={q.id ?? i} className="flex flex-col gap-2">
                    <QuoteChip quote={q} live={s.state === "live"} />
                    {canFollowUp && (
                      <Button
                        variant="secondary"
                        className="self-start px-3 py-1 text-xs"
                        onClick={() => selectedDealer && followUp(selectedDealer.id, q.property_ref ?? "")}
                      >
                        Follow up{q.property_ref ? ` on ${q.property_ref}` : ""}
                      </Button>
                    )}
                  </div>
                ));
              }
              return (
                <div className="rounded-xl border border-dashed border-border-hover bg-surface p-5">
                  <p className="font-display text-sm font-semibold text-text">Quote</p>
                  <p className="mt-2 text-sm text-text-dim">
                    {s?.state === "live" || s?.state === "calling"
                      ? "No quote logged yet — it appears here the moment the Negotiator logs one."
                      : "No quote for this dealer yet."}
                  </p>
                </div>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
