"use client";

import { useEffect } from "react";
import Script from "next/script";
import Button from "@/components/ui/Button";
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
    <div className="rounded-lg border border-line bg-panel p-6">
      <div className="mb-4 flex items-center gap-2">
        <OnAirDot />
        <span className="font-mono text-xs uppercase tracking-wide text-amber">
          Estimator · On Air
        </span>
      </div>

      {configured ? (
        <>
          <Script src={CONVAI_SCRIPT_SRC} strategy="afterInteractive" />
          <elevenlabs-convai agent-id={agentId} />
        </>
      ) : (
        <div className="rounded-md border border-dashed border-line p-4 text-sm text-muted">
          Estimator agent not configured yet (NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID
          is a placeholder). Use the buttons below.
        </div>
      )}

      <div className="mt-4 flex gap-3">
        <Button variant="secondary" onClick={simulateVoiceCompletion}>
          Simulate voice completion
        </Button>
        <Button variant="ghost" onClick={onSkip}>
          Skip voice, upload only
        </Button>
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
