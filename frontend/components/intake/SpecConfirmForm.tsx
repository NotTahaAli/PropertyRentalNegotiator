"use client";

import FieldRow from "./FieldRow";
import { SPEC_FIELD_ORDER, SPEC_FIELD_META } from "@/lib/types";
import type { JobSpec, FieldSource } from "@/lib/types";

const numberFormatter = new Intl.NumberFormat("en-PK");

interface SpecConfirmFormProps {
  spec: JobSpec;
  requiredFields: (keyof JobSpec)[];
  invalidFields: Set<keyof JobSpec>;
  onFieldChange: (key: keyof JobSpec, value: unknown) => void;
}

function formatValue(name: keyof JobSpec, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const meta = SPEC_FIELD_META[name as keyof typeof SPEC_FIELD_META];
    if (meta && meta.label.toLowerCase().includes("pkr")) {
      return `PKR ${numberFormatter.format(value)}`;
    }
    return numberFormatter.format(value);
  }
  return String(value);
}

export default function SpecConfirmForm({
  spec,
  requiredFields,
  invalidFields,
  onFieldChange,
}: SpecConfirmFormProps) {
  const budget = spec.budget_monthly_rent;
  const filledCount = SPEC_FIELD_ORDER.filter(
    (n) => spec[n] !== null && spec[n] !== undefined && spec[n] !== ""
  ).length;

  return (
    <div className="step-enter flex flex-col gap-8 lg:flex-row">
      {/* LEFT — editable fields */}
      <div className="flex flex-1 flex-col gap-3 lg:max-w-[58%]">
        {SPEC_FIELD_ORDER.map((name) => (
          <FieldRow
            key={name}
            name={name}
            meta={SPEC_FIELD_META[name as keyof typeof SPEC_FIELD_META]}
            value={spec[name]}
            source={(spec._source[name as keyof JobSpec["_source"]] ?? "unset") as FieldSource}
            required={requiredFields.includes(name)}
            invalid={invalidFields.has(name)}
            onChange={(value) => onFieldChange(name, value)}
          />
        ))}
      </div>

      {/* RIGHT — live summary panel */}
      <aside className="lg:sticky lg:top-8 lg:w-[38%] lg:self-start">
        <div className="rounded-xl border border-border bg-surface p-5">
          {/* header */}
          <div className="flex items-center justify-between border-b border-border pb-3">
            <h4 className="font-display text-sm font-semibold text-text">
              Spec summary
            </h4>
            <span className="font-mono text-xs text-text-dim">
              {filledCount}/{SPEC_FIELD_ORDER.length} filled
            </span>
          </div>

          {/* field list */}
          <div className="mt-3 flex flex-col">
            {SPEC_FIELD_ORDER.map((name) => {
              const meta = SPEC_FIELD_META[name as keyof typeof SPEC_FIELD_META];
              const val = spec[name];
              const filled = val !== null && val !== undefined && val !== "";

              return (
                <div
                  key={name}
                  className="flex items-baseline justify-between border-b border-border/50 py-2 last:border-0"
                >
                  <span className="text-xs text-text-dim">{meta.label}</span>
                  <span
                    className={`font-mono text-xs tabular-nums ${
                      filled ? "text-text" : "text-text-dim"
                    }`}
                  >
                    {formatValue(name, val)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* budget total */}
          <div className="mt-4 rounded-lg bg-accent-dim p-3.5">
            <p className="text-xs text-text-secondary">Monthly budget</p>
            <p className="mt-0.5 font-display text-lg font-bold text-accent">
              PKR {budget != null ? numberFormatter.format(budget) : "—"}
              <span className="text-sm font-normal text-text-dim"> / mo</span>
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}
