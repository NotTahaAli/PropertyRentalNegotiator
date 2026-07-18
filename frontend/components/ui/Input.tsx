import { InputHTMLAttributes } from "react";

export default function Input({
  className = "",
  invalid,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={`tr w-full rounded-lg border bg-surface px-3.5 py-2.5 text-sm text-text placeholder:text-text-dim focus:outline-none focus:ring-1 ${
        invalid
          ? "border-error/60 focus:ring-error/40"
          : "border-border hover:border-border-hover focus:border-accent/50 focus:ring-accent/30"
      } ${className}`}
      {...props}
    />
  );
}
