"use client";

import Input from "@/components/ui/Input";
import type { FieldSource, JobSpec, SpecFieldMeta } from "@/lib/types";

const SOURCE_STYLES: Record<FieldSource, { label: string; className: string }> = {
  voice: { label: "voice", className: "bg-info-dim text-info" },
  doc:   { label: "document", className: "bg-success-dim text-success" },
  manual: { label: "edited", className: "bg-elevated text-text-secondary" },
  unset: { label: "required", className: "bg-error-dim text-error" },
};

const NEIGHBOURHOODS = [
  "Gulberg III, Lahore",
  "DHA Phase 5, Lahore",
  "Clifton, Karachi",
  "Bahadurabad, Karachi",
  "F-7 Markaz, Islamabad",
  "Blue Area, Islamabad",
];

const numberFormatter = new Intl.NumberFormat("en-PK");

interface FieldRowProps {
  name: keyof JobSpec;
  meta: SpecFieldMeta;
  value: unknown;
  source: FieldSource;
  required: boolean;
  invalid: boolean;
  onChange: (value: unknown) => void;
}

export default function FieldRow({
  name,
  meta,
  value,
  source,
  required,
  invalid,
  onChange,
}: FieldRowProps) {
  const badge = SOURCE_STYLES[source];
  const showBadge = source !== "unset" || (source === "unset" && required);

  return (
    <div
      id={`field-${String(name)}`}
      className={`tr group rounded-lg border p-4 ${
        invalid
          ? "border-error/40 bg-error-dim"
          : "border-border bg-surface hover:border-border-hover"
      }`}
    >
      {/* label + badge */}
      <div className="flex items-center justify-between">
        <label
          className="text-sm font-medium text-text"
          htmlFor={`input-${String(name)}`}
        >
          {meta.label}
          {required && <span className="ml-1 text-error">*</span>}
        </label>
        {showBadge && (
          <span
            className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-medium ${badge.className}`}
          >
            {badge.label}
          </span>
        )}
      </div>

      {/* control */}
      <div className="mt-2.5">
        {meta.type === "enum" && (
          <div className="flex flex-wrap gap-2">
            {meta.values!.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => onChange(v)}
                className={`tr rounded-lg border px-3.5 py-1.5 text-sm capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  value === v
                    ? "border-primary/30 bg-primary/10 text-text"
                    : "border-border text-text-dim hover:border-border-hover hover:text-text-secondary"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        )}

        {meta.type === "bool" && (
          <div className="flex gap-2">
            {[
              { label: "Yes", v: true },
              { label: "No", v: false },
            ].map((opt) => (
              <button
                key={opt.label}
                type="button"
                onClick={() => onChange(opt.v)}
                className={`tr rounded-lg border px-3.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  value === opt.v
                    ? "border-primary/30 bg-primary/10 text-text"
                    : "border-border text-text-dim hover:border-border-hover hover:text-text-secondary"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {meta.type === "date" && (
          <Input
            id={`input-${String(name)}`}
            type="date"
            min={new Date().toISOString().slice(0, 10)}
            value={(value as string) ?? ""}
            invalid={invalid}
            onChange={(e) => onChange(e.target.value)}
          />
        )}

        {meta.type === "number" && (
          <Input
            id={`input-${String(name)}`}
            type="text"
            inputMode="numeric"
            invalid={invalid}
            className="font-mono tabular-nums"
            value={value == null ? "" : numberFormatter.format(value as number)}
            onChange={(e) => {
              const digits = e.target.value.replace(/[^0-9]/g, "");
              onChange(digits === "" ? null : Number(digits));
            }}
          />
        )}

        {meta.type === "string" && name === "location" && (
          <Input
            id={`input-${String(name)}`}
            type="text"
            list="neighbourhoods"
            invalid={invalid}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
        {meta.type === "string" && name === "location" && (
          <datalist id="neighbourhoods">
            {NEIGHBOURHOODS.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
        )}

        {meta.type === "string" && name !== "location" && (
          <Input
            id={`input-${String(name)}`}
            type="text"
            invalid={invalid}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      </div>
    </div>
  );
}
