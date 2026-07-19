export default function AudioPlayer({ url }: { url: string | null | undefined }) {
  if (!url) {
    return (
      <p className="text-xs text-text-dim">Recording unavailable for this call.</p>
    );
  }
  return (
    <div>
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-text-dim">
        Call recording · left: negotiator · right: dealer
      </p>
      <audio controls src={url} className="w-full" preload="none" />
    </div>
  );
}
