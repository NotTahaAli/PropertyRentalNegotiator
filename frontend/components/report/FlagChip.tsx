export default function FlagChip({ reason }: { reason: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="inline-flex w-fit items-center rounded-md bg-error-dim px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-error">
        Flagged
      </span>
      <p className="text-xs text-text-secondary">{reason}</p>
    </div>
  );
}
