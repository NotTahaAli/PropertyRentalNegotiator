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

// 2 rounds per master plan: round 1 (initial quote), round 2 (leverage). No round 3.
export const MAX_ROUNDS = 2;

export interface DealerCallState {
  state: UiCallState;
  round?: number; // negotiation round of the last started call (2+ = leverage round)
  callId?: string;
  startedAt?: number; // epoch ms, set when the call goes live
  transcript: TranscriptLine[];
  outcome?: CallOutcome;
  quote?: Quote | null;
  recordingUrl?: string | null;
  error?: string;
  mode?: "bridge" | "roleplay";
  negotiatorAgentId?: string;
  dynamicVariables?: Record<string, string | number | boolean>;
}

const IDLE: DealerCallState = { state: "idle", transcript: [] };

export function useCallCenter(specId: string) {
  const [dealers, setDealers] = useState<Dealer[] | null>(null);
  const [dealersError, setDealersError] = useState<string | null>(null);
  const [calls, setCalls] = useState<Record<string, DealerCallState>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [roleplay, setRoleplayMap] = useState<Record<string, boolean>>({});
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
            const quote =
              round >= 2
                ? (MOCK_QUOTES_ROUND2[dealer.persona] ?? MOCK_QUOTES[dealer.persona] ?? null)
                : (MOCK_QUOTES[dealer.persona] ?? null);
            patch(dealer.id, {
              state: "done",
              outcome,
              quote,
              recordingUrl: mockRecordingUrl(),
            });
          }
        }, MOCK_LINE_MS);
        addTimer(dealer.id, reveal);
      }, MOCK_CALLING_MS);
      addTimer(dealer.id, goLive as unknown as ReturnType<typeof setInterval>);
    },
    [patch, addTimer]
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
            // live quote: log_quote writes the row mid-call, so surface it as
            // soon as it lands instead of waiting for the call to complete
            try {
              const q = (await listQuotes(callId))[0];
              if (q) patch(dealerId, { quote: q });
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
          // completed — transcript arrives whole; fetch quote + recording.
          // quote undefined = fetch failed: keep whatever the live poll already
          // surfaced instead of clobbering it with null.
          let quote: Quote | null | undefined;
          let recordingUrl: string | null = null;
          try {
            quote = (await listQuotes(callId))[0] ?? null;
          } catch {}
          try {
            recordingUrl = await getRecordingUrl(callId);
          } catch {}
          patch(dealerId, {
            state: "done",
            transcript: call.transcript_json ?? [],
            outcome: call.outcome ?? "callback",
            ...(quote !== undefined ? { quote } : {}),
            recordingUrl,
          });
        } catch {
          // transient poll error — keep polling; surface soft error
          patch(dealerId, { error: "Status check failed — retrying..." });
        } finally {
          inFlight = false;
        }
      }, POLL_MS);
      addTimer(dealerId, poll);
    },
    [patch, addTimer, clearTimers]
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
      for (const dealer of dealers) {
        const c = latestByDealer.get(dealer.id);
        if (!c) continue;
        if (c.status === "running") {
          hydratePatch(dealer.id, {
            state: "live",
            round: c.round,
            callId: c.id,
            transcript: c.transcript_json ?? [],
          });
          pollUntilDone(dealer.id, c.id);
          continue;
        }
        let quote: Quote | null = null;
        let recordingUrl: string | null = null;
        try {
          quote = (await listQuotes(c.id))[0] ?? null;
        } catch {}
        try {
          recordingUrl = await getRecordingUrl(c.id);
        } catch {}
        if (cancelled) return;
        hydratePatch(dealer.id, {
          state: c.status === "failed" ? "failed" : "done",
          round: c.round,
          callId: c.id,
          transcript: c.transcript_json ?? [],
          outcome: c.outcome ?? (c.status === "failed" ? "failed" : "callback"),
          quote,
          recordingUrl,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dealers, specId, hydratePatch, pollUntilDone]);

  const runRealCall = useCallback(
    async (dealer: Dealer, round: number) => {
      patch(dealer.id, { state: "calling", round, mode: "bridge", transcript: [], error: undefined });
      let callId: string;
      try {
        const res = await startCall(specId, dealer.id, "bridge", round);
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
    async (dealer: Dealer, round: number) => {
      patch(dealer.id, { state: "calling", round, mode: "roleplay", transcript: [], error: undefined });
      try {
        const res = await startCall(specId, dealer.id, "roleplay", round);
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
      const quote =
        round >= 2
          ? (MOCK_QUOTES_ROUND2[dealer.persona] ?? MOCK_QUOTES[dealer.persona] ?? null)
          : (MOCK_QUOTES[dealer.persona] ?? null);
      patch(dealerId, {
        state: "done",
        round,
        transcript: lines,
        outcome,
        quote,
        recordingUrl: mockRecordingUrl(),
      });
    },
    [dealers, patch]
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
      if (!dealer) return;
      const prev = calls[dealerId];
      const current = prev?.state ?? "idle";
      if (current === "calling" || current === "live") return;
      if (current === "done" && (prev?.round ?? 1) >= MAX_ROUNDS) return; // capped, no round 3
      clearTimers(dealerId);
      setSelected(dealerId);
      const round = nextRound(dealerId);
      if (USE_MOCKS) runMockCall(dealer, round);
      else if (roleplay[dealerId]) void startRoleplay(dealer, round);
      else void runRealCall(dealer, round);
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
          quote: null,
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

  const setPersona = useCallback(
    async (dealerId: string, persona: Persona) => {
      const updated = await updateDealer(dealerId, persona);
      setDealers((prev) =>
        prev?.map((d) => (d.id === dealerId ? { ...d, persona: updated.persona } : d)) ?? prev
      );
    },
    []
  );

  const callAll = useCallback(() => {
    dealers?.forEach((d) => {
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
    callAll,
    hangUp,
    setPersona,
    roleplay,
    setRoleplay,
    finishRoleplaySession,
    seedMockCompleted,
    stateFor: (dealerId: string): DealerCallState => calls[dealerId] ?? IDLE,
  };
}
