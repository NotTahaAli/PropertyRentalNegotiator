"use client";

import { useEffect } from "react";
import Script from "next/script";
import OnAirDot from "@/components/ui/OnAirDot";
import { CONVAI_SCRIPT_SRC, getEstimatorAgentId, isAgentIdConfigured } from "@/lib/elevenlabs";
import type { JobSpec } from "@/lib/types";

// Canned fields for the "simulate" fallback — enough to demo the flow
// when the Estimator agent's tool-call shape isn't wired up yet (K3).
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
  onSkip: () => void;
}

export default function VoiceIntake({ onField, onSkip }: VoiceIntakeProps) {
  const agentId = getEstimatorAgentId();
  const configured = isAgentIdConfigured();

  useEffect(() => {
    function handleConvaiMessage(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail?.tool_name === "set_spec_field" && detail?.args?.field) {
        onField(detail.args.field as keyof JobSpec, detail.args.value);
      }
    }
    window.addEventListener("convai-message", handleConvaiMessage);
    return () => window.removeEventListener("convai-message", handleConvaiMessage);
  }, [onField]);

  function simulateVoiceCompletion() {
    for (const [key, value] of Object.entries(SIMULATED_VOICE_FIELDS)) {
      onField(key as keyof JobSpec, value);
    }
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
              spec fields automatically.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full bg-success/10 px-3 py-1.5">
            <OnAirDot />
            <span className="text-xs font-medium text-success">Live</span>
          </div>
        </div>

        {/* agent embed or placeholder */}
        {configured ? (
          <div className="mt-6">
            <Script src={CONVAI_SCRIPT_SRC} strategy="afterInteractive" />
            <elevenlabs-convai agent-id={agentId} />
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
          <button
            type="button"
            onClick={simulateVoiceCompletion}
            className="tr rounded-lg border border-border bg-elevated px-4 py-2 text-sm font-medium text-text hover:border-border-hover hover:bg-overlay active:scale-[0.98]"
          >
            Simulate voice completion
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="tr rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:text-text"
          >
            Skip to documents →
          </button>
        </div>
      </div>
    </div>
  );
}

declare module "react" {
  // eslint-disable-next-line @typescript-eslint/no-namespace -- required to augment React's JSX.IntrinsicElements
  namespace JSX {
    interface IntrinsicElements {
      "elevenlabs-convai": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & { "agent-id"?: string },
        HTMLElement
      >;
    }
  }
}
