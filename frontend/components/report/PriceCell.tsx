export default function PriceCell({
  amount,
  emphasize,
}: {
  amount: number | null;
  emphasize?: boolean;
}) {
  if (amount == null) {
    return <span className="text-sm text-text-dim">—</span>;
  }
  const formatted = new Intl.NumberFormat("en-PK").format(amount);
  return (
    <span
      className={
        emphasize
          ? "font-display text-base font-semibold text-text"
          : "text-sm text-text"
      }
    >
      PKR {formatted}
    </span>
  );
}
