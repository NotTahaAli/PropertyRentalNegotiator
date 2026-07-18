const STEPS = [
  { label: "Voice interview", short: "Voice" },
  { label: "Attach documents", short: "Docs" },
  { label: "Confirm & submit", short: "Confirm" },
] as const;

export default function StepHeader({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="anim-fade-up mb-10">
      {/* step indicators */}
      <div className="flex items-center gap-1">
        {STEPS.map((s, i) => {
          const n = (i + 1) as 1 | 2 | 3;
          const isActive = n === step;
          const isDone = n < step;

          return (
            <div key={s.short} className="flex items-center gap-1">
              {/* dot + label */}
              <div className="flex items-center gap-2">
                <div
                  className={`tr flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                    isActive
                      ? "bg-primary text-primary-fg"
                      : isDone
                        ? "bg-success/20 text-success"
                        : "bg-elevated text-text-dim"
                  }`}
                >
                  {isDone ? (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2.5 6L5 8.5L9.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : (
                    n
                  )}
                </div>
                <span
                  className={`text-sm font-medium ${
                    isActive ? "text-text" : isDone ? "text-success" : "text-text-dim"
                  }`}
                >
                  {s.short}
                </span>
              </div>

              {/* connector line */}
              {i < STEPS.length - 1 && (
                <div className="mx-3 hidden h-px w-12 sm:block md:w-20">
                  <div
                    className={`h-full ${isDone ? "bg-success/40" : "bg-border"}`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* step title */}
      <h2 className="mt-6 font-display text-2xl font-bold tracking-tight text-text sm:text-3xl">
        {STEPS[step - 1].label}
      </h2>

      {/* progress bar */}
      <div className="mt-4 h-0.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="tr h-full rounded-full bg-primary"
          style={{ width: `${(step / 3) * 100}%` }}
        />
      </div>
    </div>
  );
}
