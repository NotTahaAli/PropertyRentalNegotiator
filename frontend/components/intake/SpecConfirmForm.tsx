import FieldRow from "./FieldRow";
import { SPEC_FIELD_ORDER, SPEC_FIELD_META } from "@/lib/types";
import type { JobSpec } from "@/lib/types";

interface SpecConfirmFormProps {
  spec: JobSpec;
  requiredFields: (keyof JobSpec)[];
  invalidFields: Set<keyof JobSpec>;
  onFieldChange: (key: keyof JobSpec, value: unknown) => void;
}

export default function SpecConfirmForm({
  spec,
  requiredFields,
  invalidFields,
  onFieldChange,
}: SpecConfirmFormProps) {
  return (
    <div className="flex flex-col gap-2">
      {SPEC_FIELD_ORDER.map((name) => (
        <FieldRow
          key={name}
          name={name}
          meta={SPEC_FIELD_META[name as keyof typeof SPEC_FIELD_META]}
          value={spec[name]}
          source={spec._source[name as keyof JobSpec["_source"]] ?? "unset"}
          required={requiredFields.includes(name)}
          invalid={invalidFields.has(name)}
          onChange={(value) => onFieldChange(name, value)}
        />
      ))}
    </div>
  );
}
