"use client";

import Input from "@/components/ui/Input";
import type { FieldSource, JobSpec, SpecFieldMeta } from "@/lib/types";

const BADGE_CLASSES: Record<FieldSource, string> = {
  voice: "bg-blue/20 text-blue",
  doc: "bg-green/20 text-green",
  manual: "bg-panel-2 text-text",
  unset: "bg-panel-2 text-muted",
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
  return (
    <div
      id={`field-${String(name)}`}
      className={`flex flex-col gap-1.5 rounded-md p-3 ${invalid ? "ring-2 ring-amber" : ""}`}
    >
      <div className="flex items-center justify-between">
        <label className="text-sm text-text" htmlFor={`input-${String(name)}`}>
          {meta.label}
          {required && <span className="text-amber"> *</span>}
        </label>
        <span
          className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase ${BADGE_CLASSES[source]}`}
        >
          {source}
        </span>
      </div>

      {meta.type === "enum" && (
        <div className="flex gap-2">
          {meta.values!.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => onChange(v)}
              className={`rounded-full border px-3 py-1 text-sm capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue ${
                value === v ? "border-amber bg-amber/10 text-amber" : "border-line text-muted"
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
              className={`rounded-full border px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue ${
                value === opt.v ? "border-amber bg-amber/10 text-amber" : "border-line text-muted"
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
  );
}
