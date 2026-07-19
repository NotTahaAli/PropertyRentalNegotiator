"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { endCall, getCall, getRecordingUrl, listCalls, listDealers, listQuotes, startCall, updateDealer } from "./api";
import {
  MOCK_OUTCOMES,
  MOCK_QUOTES,
  MOCK_QUOTES_ROUND2,
  MOCK_TRANSCRIPTS,
  MOCK_TRANSCRIPTS_ROUND2,
  mockRecordingUrl,
} from "./mocks";
import type { CallOutcome, CallRow, Dealer, Persona, Quote, TranscriptLine, UiCallState } from "./types";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

const POLL_MS = 2000;
const MOCK_CALLING_MS = 2000;
const MOCK_LINE_MS = 600;

export interface DealerCallState {
  state: UiCallState;
  round?: number; // negotiation round of the last started call (2+ = leverage round)
  callId?: string;
  startedAt?: number; // epoch ms, set when the call goes live
  transcript: TranscriptLine[];
  outcome?: CallOutcome;
  // A dealer may log more than one quote (one per matching property).
  quotes: Quote[];
  callbackAt?: string | null;
  callbackNote?: string | null;
  recordingUrl?: string | null;
  error?: string;
  mode?: "bridge" | "roleplay";
  negotiatorAgentId?: string;
  dynamicVariables?: Record<string, string | number | boolean>;
}

const IDLE: DealerCallState = { state: "idle", transcript: [], quotes: [] };

// A round that doesn't re-touch a property must never make that property's
// last known quote disappear — the negotiator is now instructed to confirm
// (or update) a prior quote every follow-up call, but a call that ends early
// or covers only some properties shouldn't blank out the others. Upsert by
// property_ref instead of replacing the array wholesale.
function mergeQuotesByProperty(existing: Quote[], fresh: Quote[]): Quote[] {
  const byProp = new Map(existing.map((q) => [q.property_ref ?? "", q]));
  for (const q of fresh) byProp.set(q.property_ref ?? "", q);
  return [...byProp.values()];
}

export function useCallCenter(specId: string) {
  const [dealers, setDealers] = useState<Dealer[] | null>(null);
  const [dealersError, setDealersError] = useState<string | null>(null);
  const [calls, setCalls] = useState<Record<string, DealerCallState>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [roleplay, setRoleplayMap] = useState<Record<string, boolean>>({});
  // Every call ever made for this spec, all dealers/rounds — unlike `calls`
  // above (which only ever tracks each dealer's current/latest round), this
  // is never overwritten, so older rounds stay browsable.
  const [history, setHistory] = useState<Record<string, CallRow[]>>({});
  // Same rows, ordered exactly like the backend's report citation numbering
  // (report._call_sort_key: started_at then id, ascending) so `[call N, ...]`
  // citations can be resolved back to a dealer + call in real mode.
  const [numberedCalls, setNumberedCalls] = useState<CallRow[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setInterval>[]>>({});

  useEffect(() => {
    let cancelled = false;
    listDealers(specId)
      .then((d) => {
        if (cancelled) return;
        setDealers(d);
        if (d.length > 0) setSelected((s) => s ?? d[0].id);
      })
      .catch(() => !cancelled && setDealersError("Could not load dealers."));
    return () => {
      cancelled = true;
    };
  }, [specId]);

  // clear every timer on unmount
  useEffect(() => {
    const t = timers.current;
    return () => Object.values(t).flat().forEach(clearInterval);
  }, []);

  const patch = useCallback((dealerId: string, p: Partial<DealerCallState>) => {
    setCalls((prev) => ({ ...prev, [dealerId]: { ...(prev[dealerId] ?? IDLE), ...p } }));
  }, []);

  // only overwrites a dealer still at IDLE — never clobbers a call this
  // session already kicked off while backend history is still loading.
  const hydratePatch = useCallback((dealerId: string, p: Partial<DealerCallState>) => {
    setCalls((prev) => {
      const cur = prev[dealerId] ?? IDLE;
      if (cur.state !== "idle") return prev;
      return { ...prev, [dealerId]: { ...cur, ...p } };
    });
  }, []);

  // Like patch, but freshQuotes are upserted by property_ref onto whatever
  // quotes are already known for this dealer instead of replacing the array
  // — see mergeQuotesByProperty. Pass undefined to leave quotes untouched.
  const patchMergingQuotes = useCallback(
    (dealerId: string, fields: Partial<DealerCallState>, freshQuotes?: Quote[]) => {
      setCalls((prev) => {
        const cur = prev[dealerId] ?? IDLE;
        const quotes = freshQuotes !== undefined ? mergeQuotesByProperty(cur.quotes, freshQuotes) : cur.quotes;
        return { ...prev, [dealerId]: { ...cur, ...fields, quotes } };
      });
    },
    []
  );

  // local mirror of the backend's auto-block (see finalize_call): a call that
  // settles "declined" flips the dealer's status without waiting on a refetch.
  const markDeclined = useCallback((dealerId: string) => {
    setDealers((prev) =>
      prev?.map((d) => (d.id === dealerId ? { ...d, status: "declined" } : d)) ?? prev
    );
  }, []);

  const addTimer = useCallback((dealerId: string, id: ReturnType<typeof setInterval>) => {
    (timers.current[dealerId] ??= []).push(id);
  }, []);

  const clearTimers = useCallback((dealerId: string) => {
    (timers.current[dealerId] ?? []).forEach(clearInterval);
    timers.current[dealerId] = [];
  }, []);

  const runMockCall = useCallback(
    (dealer: Dealer, round: number) => {
      patch(dealer.id, { state: "calling", round, transcript: [], error: undefined });
      const goLive = setTimeout(() => {
        patch(dealer.id, { state: "live", startedAt: Date.now() });
        const lines =
          round >= 2
            ? (MOCK_TRANSCRIPTS_ROUND2[dealer.persona] ?? MOCK_TRANSCRIPTS[dealer.persona])
            : MOCK_TRANSCRIPTS[dealer.persona];
        let i = 0;
        const reveal = setInterval(() => {
          if (i < lines.length) {
            const next = lines[i++];
            setCalls((prev) => {
              const cur = prev[dealer.id] ?? IDLE;
              return { ...prev, [dealer.id]: { ...cur, transcript: [...cur.transcript, next] } };
            });
          } else {
            clearInterval(reveal);
            const outcome = MOCK_OUTCOMES[dealer.persona];
            const quotes =
              round >= 2
                ? (MOCK_QUOTES_ROUND2[dealer.persona] ?? MOCK_QUOTES[dealer.persona] ?? [])
                : (MOCK_QUOTES[dealer.persona] ?? []);
            patch(dealer.id, {
              state: "done",
              outcome,
              quotes,
              recordingUrl: mockRecordingUrl(),
            });
            if (outcome === "declined") markDeclined(dealer.id);
          }
        }, MOCK_LINE_MS);
        addTimer(dealer.id, reveal);
      }, MOCK_CALLING_MS);
      addTimer(dealer.id, goLive as unknown as ReturnType<typeof setInterval>);
    },
    [patch, addTimer, markDeclined]
  );

  // shared by bridge mode (polls right after POST) and roleplay (polls after
  // the human ends the voice session) — same backend statuses either way.
  const pollUntilDone = useCallback(
    (dealerId: string, callId: string) => {
      let inFlight = false; // slow backend: don't stack overlapping polls
      const poll = setInterval(async () => {
        if (inFlight) return;
        inFlight = true;
        try {
          const call = await getCall(callId);
          // poll recovered — drop a stale "retrying" banner (no-op render otherwise)
          setCalls((prev) =>
            prev[dealerId]?.error
              ? { ...prev, [dealerId]: { ...prev[dealerId], error: undefined } }
              : prev
          );
          if (call.status === "running") {
            // live quotes: log_quote writes rows mid-call, so surface them as
            // soon as they land instead of waiting for the call to complete.
            // Merged onto existing quotes — a round that hasn't (yet, or ever)
            // touched a property must not blank out its last known quote.
            try {
              const qs = await listQuotes(callId);
              if (qs.length > 0) patchMergingQuotes(dealerId, {}, qs);
            } catch {}
            return;
          }
          clearTimers(dealerId);
          if (call.status === "failed") {
            patch(dealerId, {
              state: "failed",
              outcome: "failed",
              transcript: call.transcript_json ?? [],
              error: "Call failed on the backend.",
            });
            return;
          }
          // completed — transcript arrives whole; fetch quotes + recording.
          // quotes undefined = fetch failed: keep whatever the live poll already
          // surfaced instead of clobbering it with an empty list.
          let quotes: Quote[] | undefined;
          let recordingUrl: string | null = null;
          try {
            quotes = await listQuotes(callId);
          } catch {}
          try {
            recordingUrl = await getRecordingUrl(callId);
          } catch {}
          patchMergingQuotes(
            dealerId,
            {
              state: "done",
              transcript: call.transcript_json ?? [],
              // Quotes we actually fetched outrank the stored outcome. Without
              // this, a call that produced a real itemised quote could still show
              // "Dealer asked for a callback — no numbers committed".
              // Leave undefined when the backend recorded no outcome. Defaulting to
              // "callback" made the UI assert "no numbers committed" about a call it
              // knows nothing about — a claim it can't back.
              outcome: quotes && quotes.length > 0 ? "quote" : call.outcome ?? undefined,
              recordingUrl,
              callbackAt: call.callback_at,
              callbackNote: call.callback_note,
            },
            // Merged onto whatever quotes this round already surfaced live (or
            // hydration seeded from earlier rounds) — undefined means the
            // fetch failed, so leave existing quotes alone rather than blank them.
            quotes
          );
          if (call.outcome === "declined") markDeclined(dealerId);
        } catch {
          // transient poll error — keep polling; surface soft error
          patch(dealerId, { error: "Status check failed — retrying..." });
        } finally {
          inFlight = false;
        }
      }, POLL_MS);
      addTimer(dealerId, poll);
    },
    [patch, patchMergingQuotes, addTimer, clearTimers, markDeclined]
  );

  // hydrate dealer states from real call history on load — without this the
  // calls page always shows every dealer IDLE on a fresh mount/reload, even
  // when the dashboard (which reads the same /calls endpoint) shows calls
  // already done. Mirrors dashboard.ts's deriveProgress: latest call per
  // dealer by round.
  const hydratedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!dealers || USE_MOCKS) return;
    if (hydratedFor.current === specId) return;
    hydratedFor.current = specId;
    let cancelled = false;
    (async () => {
      let rows: CallRow[];
      try {
        rows = await listCalls(specId);
      } catch {
        return;
      }
      if (cancelled) return;
      const latestByDealer = new Map<string, CallRow>();
      for (const c of rows) {
        const prev = latestByDealer.get(c.dealer_id);
        if (!prev || c.round >= prev.round) latestByDealer.set(c.dealer_id, c);
      }
      const byDealer: Record<string, CallRow[]> = {};
      for (const c of rows) {
        (byDealer[c.dealer_id] ??= []).push(c);
      }
      for (const list of Object.values(byDealer)) list.sort((a, b) => a.round - b.round);
      setHistory(byDealer);
      // report.py's _call_sort_key: (started_at ?? "", id), ascending — must
      // match exactly or a citation resolves to the wrong call.
      setNumberedCalls(
        [...rows].sort((a, b) => {
          const started = (a.started_at ?? "").localeCompare(b.started_at ?? "");
          return started !== 0 ? started : a.id.localeCompare(b.id);
        })
      );
      for (const dealer of dealers) {
        const c = latestByDealer.get(dealer.id);
        if (!c) continue;
        // Merge every one of this dealer's rounds' quotes, oldest first, so a
        // round that hasn't (yet, or ever) re-touched a property doesn't make
        // that property's last known quote disappear on reload — see
        // mergeQuotesByProperty. The live/latest call, if still running, is
        // skipped here and fetched instead by pollUntilDone below.
        let quotes: Quote[] = [];
        for (const call of byDealer[dealer.id] ?? []) {
          if (call.id === c.id && call.status === "running") continue;
          try {
            quotes = mergeQuotesByProperty(quotes, await listQuotes(call.id));
          } catch {}
        }
        if (cancelled) return;
        if (c.status === "running") {
          hydratePatch(dealer.id, {
            state: "live",
            round: c.round,
            callId: c.id,
            transcript: c.transcript_json ?? [],
            quotes,
          });
          pollUntilDone(dealer.id, c.id);
          continue;
        }
        let recordingUrl: string | null = null;
        try {
          recordingUrl = await getRecordingUrl(c.id);
        } catch {}
        if (cancelled) return;
        hydratePatch(dealer.id, {
          state: c.status === "failed" ? "failed" : "done",
          round: c.round,
          callId: c.id,
          transcript: c.transcript_json ?? [],
          // same rule as the poll path: a real quote row beats the stored outcome
          outcome:
            c.status === "failed"
              ? "failed"
              : quotes.length > 0
                ? "quote"
                : c.outcome ?? undefined,
          quotes,
          recordingUrl,
          callbackAt: c.callback_at,
          callbackNote: c.callback_note,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dealers, specId, hydratePatch, pollUntilDone]);

  const runRealCall = useCallback(
    async (dealer: Dealer, round: number, focusPropertyRef?: string) => {
      patch(dealer.id, { state: "calling", round, mode: "bridge", transcript: [], error: undefined });
      let callId: string;
      try {
        const res = await startCall(specId, dealer.id, "bridge", round, focusPropertyRef);
        callId = res.call_id;
      } catch {
        patch(dealer.id, { state: "failed", error: "Could not start call — backend unreachable?" });
        return;
      }
      patch(dealer.id, { state: "live", callId, startedAt: Date.now() });
      pollUntilDone(dealer.id, callId);
    },
    [specId, patch, pollUntilDone]
  );

  const startRoleplay = useCallback(
    async (dealer: Dealer, round: number, focusPropertyRef?: string) => {
      patch(dealer.id, { state: "calling", round, mode: "roleplay", transcript: [], error: undefined });
      try {
        const res = await startCall(specId, dealer.id, "roleplay", round, focusPropertyRef);
        patch(dealer.id, {
          state: "live",
          callId: res.call_id,
          startedAt: Date.now(),
          negotiatorAgentId: res.negotiator_agent_id,
          dynamicVariables: res.dynamic_variables as Record<string, string | number | boolean> | undefined,
        });
      } catch {
        patch(dealer.id, { state: "failed", error: "Could not start roleplay call — backend unreachable?" });
      }
    },
    [specId, patch]
  );

  // called when the human ends the ElevenLabs voice session (onDisconnect)
  const finishRoleplaySession = useCallback(
    (dealerId: string) => {
      const callId = calls[dealerId]?.callId;
      if (!callId) return;
      pollUntilDone(dealerId, callId);
    },
    [calls, pollUntilDone]
  );

  const setRoleplay = useCallback((dealerId: string, on: boolean) => {
    setRoleplayMap((prev) => ({ ...prev, [dealerId]: on }));
  }, []);

  // Mock-only: instantly seeds a dealer as "done" for a given round, for the
  // report's citation deep-link (?call=&line=) — same source data and same
  // branch logic as runMockCall's completion, just synchronous instead of
  // timer-driven. Never call this outside USE_MOCKS; there is no real-data
  // equivalent, and faking a completed call in real mode would hide missing
  // backend state instead of surfacing it.
  const seedMockCompleted = useCallback(
    (dealerId: string, round: number) => {
      const dealer = dealers?.find((d) => d.id === dealerId);
      if (!dealer) return;
      const lines =
        round >= 2
          ? (MOCK_TRANSCRIPTS_ROUND2[dealer.persona] ?? MOCK_TRANSCRIPTS[dealer.persona])
          : MOCK_TRANSCRIPTS[dealer.persona];
      const outcome = MOCK_OUTCOMES[dealer.persona];
      const quotes =
        round >= 2
          ? (MOCK_QUOTES_ROUND2[dealer.persona] ?? MOCK_QUOTES[dealer.persona] ?? [])
          : (MOCK_QUOTES[dealer.persona] ?? []);
      patch(dealerId, {
        state: "done",
        round,
        transcript: lines,
        outcome,
        quotes,
        recordingUrl: mockRecordingUrl(),
      });
      if (outcome === "declined") markDeclined(dealerId);
    },
    [dealers, patch, markDeclined]
  );

  // a completed call bumps the next one to a leverage round; retries keep their round
  const nextRound = useCallback(
    (dealerId: string) => {
      const prev = calls[dealerId];
      return prev?.state === "done" ? (prev.round ?? 1) + 1 : (prev?.round ?? 1);
    },
    [calls]
  );

  const call = useCallback(
    (dealerId: string) => {
      const dealer = dealers?.find((d) => d.id === dealerId);
      if (!dealer || dealer.status === "declined") return;
      const prev = calls[dealerId];
      const current = prev?.state ?? "idle";
      if (current === "calling" || current === "live") return;
      clearTimers(dealerId);
      setSelected(dealerId);
      const round = nextRound(dealerId);
      if (USE_MOCKS) runMockCall(dealer, round);
      else if (roleplay[dealerId]) void startRoleplay(dealer, round);
      else void runRealCall(dealer, round);
    },
    [dealers, calls, clearTimers, runMockCall, runRealCall, startRoleplay, roleplay, nextRound]
  );

  // Scoped follow-up: same guard rule as call() (rounds are unlimited, a
  // declined dealer can't be re-called), but targets one of the dealer's
  // several properties (focus_property_ref) instead of the dealer as a whole.
  const followUp = useCallback(
    (dealerId: string, propertyRef: string) => {
      const dealer = dealers?.find((d) => d.id === dealerId);
      if (!dealer || dealer.status === "declined") return;
      const prev = calls[dealerId];
      const current = prev?.state ?? "idle";
      if (current === "calling" || current === "live") return;
      clearTimers(dealerId);
      setSelected(dealerId);
      const round = nextRound(dealerId);
      if (USE_MOCKS) runMockCall(dealer, round);
      else if (roleplay[dealerId]) void startRoleplay(dealer, round, propertyRef);
      else void runRealCall(dealer, round, propertyRef);
    },
    [dealers, calls, clearTimers, runMockCall, runRealCall, startRoleplay, roleplay, nextRound]
  );

  // manual early hang-up. Mock: settle the call locally. Bridge: ask the
  // backend to stop; the already-running status poll picks up "completed".
  // Roleplay hangs up through its own session controls, not here.
  const hangUp = useCallback(
    (dealerId: string) => {
      const cur = calls[dealerId];
      if (cur?.state !== "live") return;
      if (USE_MOCKS) {
        clearTimers(dealerId);
        patch(dealerId, {
          state: "done",
          outcome: "callback",
          quotes: [],
          recordingUrl: mockRecordingUrl(),
        });
        return;
      }
      if (cur.mode === "bridge" && cur.callId) {
        void endCall(cur.callId).catch(() => {
          patch(dealerId, { error: "Could not end the call — it may finish on its own." });
        });
      }
    },
    [calls, clearTimers, patch]
  );

  // "Search more dealers" — appends newly discovered dealers, skipping any id
  // already in the list (double-click safety; the backend also dedupes by name).
  const addDealers = useCallback((found: Dealer[]) => {
    setDealers((prev) => {
      const existing = new Set((prev ?? []).map((d) => d.id));
      const fresh = found.filter((d) => !existing.has(d.id));
      return [...(prev ?? []), ...fresh];
    });
  }, []);

  const setPersona = useCallback(
    async (dealerId: string, persona: Persona) => {
      const updated = await updateDealer(dealerId, { persona });
      setDealers((prev) =>
        prev?.map((d) => (d.id === dealerId ? { ...d, persona: updated.persona } : d)) ?? prev
      );
    },
    []
  );

  const setDealerStatus = useCallback(
    async (dealerId: string, status: "active" | "declined") => {
      const updated = await updateDealer(dealerId, { status });
      setDealers((prev) =>
        prev?.map((d) => (d.id === dealerId ? { ...d, status: updated.status } : d)) ?? prev
      );
    },
    []
  );

  const resolveCallNumber = useCallback(
    (n: number): CallRow | undefined => numberedCalls[n - 1],
    [numberedCalls]
  );

  const callAll = useCallback(() => {
    dealers?.forEach((d) => {
      if (d.status === "declined") return;
      const s = calls[d.id]?.state ?? "idle";
      if (s !== "idle" && s !== "failed") return;
      if (USE_MOCKS) runMockCall(d, nextRound(d.id));
      // roleplay needs a human on the line for each call — bulk-start skips those,
      // they're started individually from the DealerCard button instead.
      else if (!roleplay[d.id]) void runRealCall(d, nextRound(d.id));
    });
  }, [dealers, calls, runMockCall, runRealCall, roleplay, nextRound]);

  return {
    dealers,
    dealersError,
    calls,
    selected,
    select: setSelected,
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
    stateFor: (dealerId: string): DealerCallState => calls[dealerId] ?? IDLE,
    historyFor: (dealerId: string): CallRow[] => history[dealerId] ?? [],
    resolveCallNumber,
  };
}
