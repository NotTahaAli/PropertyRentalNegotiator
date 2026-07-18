export default function OnAirDot() {
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber opacity-75" />
      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber" />
    </span>
  );
}
