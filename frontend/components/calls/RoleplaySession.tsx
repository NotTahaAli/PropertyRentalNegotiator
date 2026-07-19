"use client";

import { useCallback, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import Button from "@/components/ui/Button";
import OnAirDot from "@/components/ui/OnAirDot";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

interface RoleplaySessionProps {
  agentId?: string;
  dynamicVariables?: Record<string, string | number | boolean>;
  onEnded: () => void;
}

export default function RoleplaySession({ agentId, dynamicVariables, onEnded }: RoleplaySessionProps) {
  const [ended, setEnded] = useState(false);

  if (USE_MOCKS || !agentId) {
    return (
      <div className="rounded-xl border border-dashed border-border-hover bg-elevated p-5">
        <p className="text-sm text-text-dim">
          Voice available when agent IDs are wired. In mock mode the call
          completes on its own — read the character card, the transcript
          streams in without any action needed here.
        </p>
      </div>
    );
  }

  if (ended) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5">
        <p className="rec-pulse text-sm text-text-secondary">
          Call ended — waiting for the transcript to finalize...
        </p>
      </div>
    );
  }

  return (
    <ConversationProvider
      agentId={agentId}
      dynamicVariables={dynamicVariables}
      onDisconnect={() => {
        setEnded(true);
        onEnded();
      }}
    >
      <RoleplaySessionInner />
    </ConversationProvider>
  );
}

function RoleplaySessionInner() {
  const [error, setError] = useState<string | null>(null);
  const { startSession, endSession, status, isSpeaking } = useConversation({
    onError: () => setError("Voice connection failed."),
  });
  const connected = status === "connected";

  const connect = useCallback(async () => {
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      startSession();
    } catch {
      setError("Microphone unavailable.");
    }
  }, [startSession]);

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="font-display text-sm font-semibold text-text">Negotiator call</p>
        {connected && (
          <div className="flex items-center gap-2 rounded-full bg-success/10 px-3 py-1.5">
            <OnAirDot />
            <span className="text-xs font-medium text-success">
              {isSpeaking ? "Negotiator speaking" : "Listening..."}
            </span>
          </div>
        )}
      </div>
      <p className="mt-2 text-xs text-text-dim">
        Speak as the dealer, reading from the character card. Click End call
        once the negotiation concludes.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {connected ? (
          <Button variant="secondary" onClick={() => endSession()}>
            End call
          </Button>
        ) : (
          <Button onClick={connect} disabled={status === "connecting"}>
            {status === "connecting" ? "Connecting..." : "Connect voice"}
          </Button>
        )}
        {error && <p className="text-sm text-text-dim">{error}</p>}
      </div>
    </div>
  );
}
