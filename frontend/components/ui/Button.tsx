import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-fg hover:opacity-90 active:scale-[0.98]",
  secondary:
    "border border-border bg-surface text-text hover:border-border-hover hover:bg-elevated active:scale-[0.98]",
  ghost:
    "text-text-secondary hover:text-text",
};

export default function Button({
  variant = "primary",
  className = "",
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`tr inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 font-display text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-40 ${VARIANT_CLASSES[variant]} ${className}`}
      disabled={disabled}
      {...props}
    />
  );
}
