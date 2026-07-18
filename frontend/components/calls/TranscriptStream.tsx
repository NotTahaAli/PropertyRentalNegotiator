"use client";

import { useEffect, useRef } from "react";
import type { TranscriptLine } from "@/lib/types";

export default function TranscriptStream({ lines }: { lines: TranscriptLine[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [lines.length]);

  if (lines.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-text-dim">
        Transcript appears here once the conversation starts.
      </p>
    );
  }

  return (
    <div className="max-h-80 overflow-y-auto pr-1">
      <div className="flex flex-col gap-2.5">
        {lines.map((l) => (
          <div key={l.line} className="anim-fade-in flex gap-2.5 text-sm">
            <span className="shrink-0 pt-0.5 font-mono text-[10px] tabular-nums text-text-dim">
              [{l.line}]
            </span>
            <div className="min-w-0">
              <span
                className={`font-mono text-[10px] font-medium uppercase tracking-wide ${
                  l.speaker === "negotiator" ? "text-info" : "text-accent"
                }`}
              >
                {l.speaker}
              </span>
              <p className="mt-0.5 leading-relaxed text-text-secondary">{l.text}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
