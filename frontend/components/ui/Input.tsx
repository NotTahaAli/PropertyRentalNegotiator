import { InputHTMLAttributes } from "react";

export default function Input({
  className = "",
  invalid,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={`w-full rounded-md border bg-panel-2 px-3 py-2 text-text placeholder:text-muted focus:outline-none focus:ring-2 ${
        invalid ? "border-amber ring-amber" : "border-line ring-blue"
      } ${className}`}
      {...props}
    />
  );
}
