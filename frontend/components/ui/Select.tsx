import { SelectHTMLAttributes } from "react";

export default function Select({
  className = "",
  invalid,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      className={`w-full rounded-md border bg-panel-2 px-3 py-2 text-text focus:outline-none focus:ring-2 ${
        invalid ? "border-amber ring-amber" : "border-line ring-blue"
      } ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}
