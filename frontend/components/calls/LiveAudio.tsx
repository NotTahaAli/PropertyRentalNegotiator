"use client";

import { useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/components/auth/AuthProvider";

const WS_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(
  /^http/,
  "ws"
);
const SAMPLE_RATE = 16000; // backend bridge AUDIO_FORMAT pcm_16000

type Leg = "negotiator" | "dealer";
const LEGS: Leg[] = ["negotiator", "dealer"];
// ponytail: fixed pan, negotiator left / dealer right — matches the recording's channels
const PAN: Record<Leg, number> = { negotiator: -0.7, dealer: 0.7 };

export default function LiveAudio({ callId }: { callId: string }) {
  const [muted, setMuted] = useState<Record<Leg, boolean>>({
    negotiator: false,
    dealer: false,
  });
  const [connected, setConnected] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const gainsRef = useRef<Record<Leg, GainNode> | null>(null);

  useEffect(() => {
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    ctxRef.current = ctx;
    const gains = {} as Record<Leg, GainNode>;
    for (const leg of LEGS) {
      const gain = ctx.createGain();
      const pan = new StereoPannerNode(ctx, { pan: PAN[leg] });
      gain.connect(pan).connect(ctx.destination);
      gains[leg] = gain;
    }
    gainsRef.current = gains;

    // per-leg playback cursor so chunks of the same leg queue back-to-back
    const nextAt: Record<Leg, number> = { negotiator: 0, dealer: 0 };
    let ws: WebSocket | null = null;
    let cancelled = false;

    (async () => {
      const token = await getAccessToken();
      if (cancelled || !token) return;
      ws = new WebSocket(
        `${WS_BASE}/calls/${encodeURIComponent(callId)}/stream?token=${encodeURIComponent(token)}`
      );
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (e) => {
        if (ctx.state === "suspended") void ctx.resume();
        let leg: Leg, audio: string;
        try {
          ({ leg, audio } = JSON.parse(e.data));
        } catch {
          return;
        }
        if (!gains[leg]) return;
        const bytes = Uint8Array.from(atob(audio), (c) => c.charCodeAt(0));
        const pcm = new Int16Array(bytes.buffer, 0, bytes.byteLength >> 1);
        if (pcm.length === 0) return;
        const buf = ctx.createBuffer(1, pcm.length, SAMPLE_RATE);
        const ch = buf.getChannelData(0);
        for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(gains[leg]);
        const at = Math.max(ctx.currentTime, nextAt[leg]);
        src.start(at);
        nextAt[leg] = at + buf.duration;
      };
    })();

    return () => {
      cancelled = true;
      ws?.close();
      void ctx.close();
    };
  }, [callId]);

  const toggle = (leg: Leg) => {
    // mute click is also the user gesture that unlocks audio if autoplay blocked it
    if (ctxRef.current?.state === "suspended") void ctxRef.current.resume();
    setMuted((m) => {
      const next = { ...m, [leg]: !m[leg] };
      const gain = gainsRef.current?.[leg];
      if (gain) gain.gain.value = next[leg] ? 0 : 1;
      return next;
    });
  };

  return (
    <div className="mb-3 rounded-lg border border-border bg-elevated px-3 py-2">
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-text-dim">
        Live audio {connected ? "· streaming" : "· connecting..."}
      </p>
      <div className="flex gap-2">
        {LEGS.map((leg) => (
          <button
            key={leg}
            type="button"
            onClick={() => toggle(leg)}
            className={`rounded-md border border-border px-2.5 py-1 text-xs capitalize ${
              muted[leg] ? "text-text-dim line-through" : "text-text-secondary"
            }`}
          >
            {leg === "negotiator" ? "Negotiator (L)" : "Dealer (R)"}
          </button>
        ))}
      </div>
    </div>
  );
}
