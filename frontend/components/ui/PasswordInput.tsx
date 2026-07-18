"use client";

import { InputHTMLAttributes, useState } from "react";
import Input from "./Input";

export default function PasswordInput(
  props: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
    invalid?: boolean;
  }
) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <Input {...props} type={visible ? "text" : "password"} className="pr-11" />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="tr absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-text-dim hover:text-text-secondary"
      >
        {visible ? (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M2 2l12 12M6.5 6.6A2 2 0 009.4 9.5M4.2 4.5C2.9 5.4 2 6.6 1.5 8c1 2.8 3.5 4.5 6.5 4.5 1.2 0 2.3-.3 3.3-.8m1.9-1.4c.6-.6 1.1-1.4 1.3-2.3-1-2.8-3.5-4.5-6.5-4.5-.5 0-1 .1-1.5.2"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M1.5 8C2.5 5.2 5 3.5 8 3.5s5.5 1.7 6.5 4.5c-1 2.8-3.5 4.5-6.5 4.5S2.5 10.8 1.5 8z"
              stroke="currentColor"
              strokeWidth="1.3"
            />
            <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
          </svg>
        )}
      </button>
    </div>
  );
}
