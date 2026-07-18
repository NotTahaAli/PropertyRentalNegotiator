import { SelectHTMLAttributes } from "react";

export default function Select({
  className = "",
  invalid,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      className={`tr w-full rounded-lg border bg-surface px-3.5 py-2.5 text-sm text-text focus:outline-none focus:ring-1 ${
        invalid
          ? "border-error/60 focus:ring-error/40"
          : "border-border hover:border-border-hover focus:border-accent/50 focus:ring-accent/30"
      } ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}
