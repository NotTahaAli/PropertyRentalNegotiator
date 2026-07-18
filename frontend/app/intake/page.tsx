"use client";

import { useReducer, useState } from "react";
import { useRouter } from "next/navigation";
import StepHeader from "@/components/intake/StepHeader";
import VoiceIntake from "@/components/intake/VoiceIntake";
import DocUpload from "@/components/intake/DocUpload";
import SpecConfirmForm from "@/components/intake/SpecConfirmForm";
import ConfirmBar from "@/components/intake/ConfirmBar";
import Button from "@/components/ui/Button";
import { submitSpec } from "@/lib/api";
import { MOCK_SPEC } from "@/lib/mocks";
import { REQUIRED_SPEC_FIELDS } from "@/lib/types";
import type { JobSpec, ParsedDoc, FieldSource } from "@/lib/types";

// Fields where a parsed document overrides voice; everything else, voice wins.
// Manual edits always win regardless of group.
const DOC_PRIORITY_FIELDS: (keyof JobSpec)[] = ["area_sqft", "frontage_ft", "current_rent"];

function sourcePriority(field: keyof JobSpec): FieldSource[] {
  return DOC_PRIORITY_FIELDS.includes(field)
    ? ["manual", "doc", "voice"]
    : ["manual", "voice", "doc"];
}

function applyField(spec: JobSpec, key: keyof JobSpec, value: unknown, from: FieldSource): JobSpec {
  const order = sourcePriority(key);
  const current = spec._source[key as keyof JobSpec["_source"]] ?? "unset";
  const currentRank = order.indexOf(current);
  const newRank = order.indexOf(from);
  if (newRank === -1 || (currentRank !== -1 && newRank > currentRank)) return spec;
  return {
    ...spec,
    [key]: value,
    _source: { ...spec._source, [key]: from },
  };
}

type State = { step: 1 | 2 | 3; spec: JobSpec };

type Action =
  | { type: "VOICE_FIELD"; key: keyof JobSpec; value: unknown }
  | { type: "DOC_PARSED"; parsed: ParsedDoc }
  | { type: "MANUAL_EDIT"; key: keyof JobSpec; value: unknown }
  | { type: "GOTO"; step: 1 | 2 | 3 };

const EMPTY_SPEC: JobSpec = {
  vertical: "commercial_shop_rental_pk",
  currency: "PKR",
  area_sqft: null,
  location: "",
  floor: null,
  business_type: "",
  frontage_ft: null,
  lease_years: null,
  parking: null,
  move_in: null,
  current_rent: null,
  budget_monthly_rent: null,
  _source: {},
};

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "VOICE_FIELD":
      return { ...state, spec: applyField(state.spec, action.key, action.value, "voice") };
    case "DOC_PARSED": {
      let spec = state.spec;
      for (const [key, value] of Object.entries(action.parsed.partial_spec)) {
        spec = applyField(spec, key as keyof JobSpec, value, "doc");
      }
      return { ...state, spec };
    }
    case "MANUAL_EDIT":
      return {
        ...state,
        spec: {
          ...state.spec,
          [action.key]: action.value,
          _source: { ...state.spec._source, [action.key]: "manual" },
        },
      };
    case "GOTO":
      return { ...state, step: action.step };
    default:
      return state;
  }
}

function isFieldMissing(spec: JobSpec, key: keyof JobSpec): boolean {
  const value = spec[key];
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  return false;
}

export default function IntakePage() {
  const router = useRouter();
  const [{ step, spec }, dispatch] = useReducer(reducer, {
    step: 1,
    spec: USE_MOCKS ? MOCK_SPEC : EMPTY_SPEC,
  });
  const [invalidFields, setInvalidFields] = useState<Set<keyof JobSpec>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleConfirm() {
    const missing = REQUIRED_SPEC_FIELDS.filter((f) => isFieldMissing(spec, f));
    if (missing.length > 0) {
      setInvalidFields(new Set(missing));
      document
        .getElementById(`field-${String(missing[0])}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setInvalidFields(new Set());
    setSubmitError(null);
    setSubmitting(true);
    try {
      const res = await submitSpec(spec);
      router.push(`/calls/${res.spec_id}`);
    } catch {
      setSubmitError("Could not submit spec. Check the backend and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <StepHeader step={step} />

      {step === 1 && (
        <VoiceIntake
          onField={(key, value) => dispatch({ type: "VOICE_FIELD", key, value })}
          onCallEnded={() => dispatch({ type: "GOTO", step: 2 })}
          onAddDocs={() => dispatch({ type: "GOTO", step: 2 })}
        />
      )}

      {step === 2 && (
        <div className="step-enter flex flex-col gap-6">
          <DocUpload onParsed={(parsed) => dispatch({ type: "DOC_PARSED", parsed })} />
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => dispatch({ type: "GOTO", step: 1 })}>
              ← Back to voice
            </Button>
            <Button
              variant="secondary"
              onClick={() => dispatch({ type: "GOTO", step: 3 })}
            >
              Continue to confirm →
            </Button>
          </div>
        </div>
      )}

      {step === 3 && (
        <>
          <SpecConfirmForm
            spec={spec}
            requiredFields={REQUIRED_SPEC_FIELDS}
            invalidFields={invalidFields}
            onFieldChange={(key, value) => dispatch({ type: "MANUAL_EDIT", key, value })}
          />
          {submitError && (
            <p role="alert" className="mt-3 text-sm text-error">
              {submitError}
            </p>
          )}
          <ConfirmBar
            onBack={() => dispatch({ type: "GOTO", step: 2 })}
            onConfirm={handleConfirm}
            submitting={submitting}
          />
        </>
      )}
    </div>
  );
}
