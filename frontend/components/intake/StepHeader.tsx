const STEPS = ["Voice", "Docs", "Confirm"] as const;

export default function StepHeader({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="mb-8 flex items-center gap-3 font-mono text-xs uppercase tracking-wide">
      {STEPS.map((label, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        const active = n === step;
        const done = n < step;
        return (
          <div key={label} className="flex items-center gap-3">
            <span
              className={
                active
                  ? "text-amber"
                  : done
                    ? "text-green"
                    : "text-muted"
              }
            >
              {n}. {label}
            </span>
            {i < STEPS.length - 1 && <span className="text-line">/</span>}
          </div>
        );
      })}
    </div>
  );
}
