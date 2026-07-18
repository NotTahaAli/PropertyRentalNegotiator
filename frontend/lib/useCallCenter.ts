"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCall, getRecordingUrl, listDealers, listQuotes, startCall } from "./api";
import { MOCK_OUTCOMES, MOCK_QUOTES, MOCK_TRANSCRIPTS, mockRecordingUrl } from "./mocks";
import type { CallOutcome, Dealer, Quote, TranscriptLine, UiCallState } from "./types";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

const POLL_MS = 2000;
const MOCK_CALLING_MS = 2000;
const MOCK_LINE_MS = 600;

export interface DealerCallState {
  state: UiCallState;
  callId?: string;
  startedAt?: number; // epoch ms, set when the call goes live
  transcript: TranscriptLine[];
  outcome?: CallOutcome;
  quote?: Quote | null;
  recordingUrl?: string | null;
  error?: string;
}

const IDLE: DealerCallState = { state: "idle", transcript: [] };

export function useCallCenter(specId: string) {
  const [dealers, setDealers] = useState<Dealer[] | null>(null);
  const [dealersError, setDealersError] = useState<string | null>(null);
  const [calls, setCalls] = useState<Record<string, DealerCallState>>({});
  const [selected, setSelected] = useState<string | null>(null);
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

  const addTimer = useCallback((dealerId: string, id: ReturnType<typeof setInterval>) => {
    (timers.current[dealerId] ??= []).push(id);
  }, []);

  const clearTimers = useCallback((dealerId: string) => {
    (timers.current[dealerId] ?? []).forEach(clearInterval);
    timers.current[dealerId] = [];
  }, []);

  const runMockCall = useCallback(
    (dealer: Dealer) => {
      patch(dealer.id, { state: "calling", transcript: [], error: undefined });
      const goLive = setTimeout(() => {
        patch(dealer.id, { state: "live", startedAt: Date.now() });
        const lines = MOCK_TRANSCRIPTS[dealer.persona];
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
            patch(dealer.id, {
              state: "done",
              outcome,
              quote: MOCK_QUOTES[dealer.persona] ?? null,
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

  const runRealCall = useCallback(
    async (dealer: Dealer) => {
      patch(dealer.id, { state: "calling", transcript: [], error: undefined });
      let callId: string;
      try {
        const res = await startCall(specId, dealer.id, "bridge");
        callId = res.call_id;
      } catch {
        patch(dealer.id, { state: "failed", error: "Could not start call — backend unreachable?" });
        return;
      }
      patch(dealer.id, { state: "live", callId, startedAt: Date.now() });

      const poll = setInterval(async () => {
        try {
          const call = await getCall(callId);
          if (call.status === "running") return;
          clearTimers(dealer.id);
          if (call.status === "failed") {
            patch(dealer.id, {
              state: "failed",
              outcome: "failed",
              transcript: call.transcript_json ?? [],
              error: "Call failed on the backend.",
            });
            return;
          }
          // completed — transcript arrives whole; fetch quote + recording
          let quote: Quote | null = null;
          let recordingUrl: string | null = null;
          try {
            const quotes = await listQuotes(callId);
            quote = quotes[0] ?? null;
          } catch {}
          try {
            recordingUrl = await getRecordingUrl(callId);
          } catch {}
          patch(dealer.id, {
            state: "done",
            transcript: call.transcript_json ?? [],
            outcome: call.outcome ?? "callback",
            quote,
            recordingUrl,
          });
        } catch {
          // transient poll error — keep polling; surface soft error
          patch(dealer.id, { error: "Status check failed — retrying..." });
        }
      }, POLL_MS);
      addTimer(dealer.id, poll);
    },
    [specId, patch, addTimer, clearTimers]
  );

  const call = useCallback(
    (dealerId: string) => {
      const dealer = dealers?.find((d) => d.id === dealerId);
      if (!dealer) return;
      const current = calls[dealerId]?.state ?? "idle";
      if (current === "calling" || current === "live") return;
      clearTimers(dealerId);
      setSelected(dealerId);
      if (USE_MOCKS) runMockCall(dealer);
      else void runRealCall(dealer);
    },
    [dealers, calls, clearTimers, runMockCall, runRealCall]
  );

  const callAll = useCallback(() => {
    dealers?.forEach((d) => {
      const s = calls[d.id]?.state ?? "idle";
      if (s === "idle" || s === "failed") {
        if (USE_MOCKS) runMockCall(d);
        else void runRealCall(d);
      }
    });
  }, [dealers, calls, runMockCall, runRealCall]);

  return {
    dealers,
    dealersError,
    calls,
    selected,
    select: setSelected,
    call,
    callAll,
    stateFor: (dealerId: string): DealerCallState => calls[dealerId] ?? IDLE,
  };
}
