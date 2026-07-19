"use client";

import { useCallback, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import Button from "@/components/ui/Button";
import OnAirDot from "@/components/ui/OnAirDot";
import { getEstimatorAgentId, isAgentIdConfigured } from "@/lib/elevenlabs";
import type { JobSpec } from "@/lib/types";

// Canned fields for the "simulate" fallback — demo without spending credits.
const SIMULATED_VOICE_FIELDS: Partial<
  Record<Exclude<keyof JobSpec, "_source" | "id" | "vertical" | "currency">, unknown>
> = {
  location: "Gulberg III, Lahore",
  floor: "ground",
  business_type: "electronics retail",
  lease_years: 3,
  parking: true,
  move_in: "2026-08-01",
  budget_monthly_rent: 95000,
};

interface VoiceIntakeProps {
  onField: (key: keyof JobSpec, value: unknown) => void;
  onCallEnded: () => void;
  onAddDocs: () => void;
}

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

export default function VoiceIntake(props: VoiceIntakeProps) {
  return (
    <ConversationProvider
      agentId={getEstimatorAgentId()}
      clientTools={{
        // Estimator agent tool: any subset of spec fields, typed by the tool schema.
        set_spec_field: (params: Record<string, unknown>) => {
          for (const [key, value] of Object.entries(params)) {
            props.onField(key as keyof JobSpec, value);
          }
          return "recorded";
        },
      }}
      onDisconnect={props.onCallEnded}
    >
      <VoiceIntakeInner {...props} />
    </ConversationProvider>
  );
}

function VoiceIntakeInner({ onField, onCallEnded, onAddDocs }: VoiceIntakeProps) {
  const configured = isAgentIdConfigured();
  const [error, setError] = useState<string | null>(null);

  const { startSession, endSession, status, isSpeaking } = useConversation({
    onError: () =>
      setError("Voice connection failed. You can continue with documents instead."),
  });

  const startInterview = useCallback(async () => {
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      startSession();
    } catch {
      setError("Microphone unavailable. You can continue with documents instead.");
    }
  }, [startSession]);

  const connected = status === "connected";

  function simulateVoiceCompletion() {
    for (const [key, value] of Object.entries(SIMULATED_VOICE_FIELDS)) {
      onField(key as keyof JobSpec, value);
    }
    onCallEnded();
  }

  return (
    <div className="step-enter">
      {/* interview area */}
      <div className="rounded-xl border border-border bg-surface p-6 sm:p-8">
        {/* header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-display text-lg font-semibold text-text">
              Tell the estimator what you need
            </h3>
            <p className="mt-1.5 max-w-lg text-sm leading-relaxed text-text-secondary">
              Describe your requirements and the voice agent will fill in the
              spec fields automatically. When the call ends you can optionally
              attach documents, then review everything before submitting.
            </p>
          </div>
          {connected && (
            <div className="flex items-center gap-2 rounded-full bg-success/10 px-3 py-1.5">
              <OnAirDot />
              <span className="text-xs font-medium text-success">
                {isSpeaking ? "Estimator speaking" : "Listening..."}
              </span>
            </div>
          )}
        </div>

        {/* call controls or placeholder */}
        {configured ? (
          <div className="mt-6 flex flex-wrap items-center gap-3">
            {connected ? (
              <Button variant="secondary" onClick={() => endSession()}>
                End interview
              </Button>
            ) : (
              <Button onClick={startInterview} disabled={status === "connecting"}>
                {status === "connecting" ? "Connecting..." : "Start interview"}
              </Button>
            )}
            {error && <p className="text-sm text-text-dim">{error}</p>}
          </div>
        ) : (
          <div className="mt-6 rounded-lg border border-dashed border-border-hover bg-elevated p-5">
            <p className="text-sm text-text-dim">
              Estimator agent not configured yet. The agent ID is a placeholder.
              Use the actions below to continue.
            </p>
          </div>
        )}

        {/* actions */}
        <div className="mt-6 flex flex-wrap gap-3">
          {USE_MOCKS && (
            <button
              type="button"
              onClick={simulateVoiceCompletion}
              className="tr rounded-lg border border-border bg-elevated px-4 py-2 text-sm font-medium text-text hover:border-border-hover hover:bg-overlay active:scale-[0.98]"
            >
              Simulate voice completion
            </button>
          )}
          <button
            type="button"
            onClick={onAddDocs}
            className="tr rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:text-text"
          >
            Continue to documents →
          </button>
        </div>
      </div>
    </div>
  );
}
