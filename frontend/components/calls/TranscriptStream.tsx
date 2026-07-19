"use client";

import { useEffect, useRef } from "react";
import type { TranscriptLine } from "@/lib/types";

interface TranscriptStreamProps {
  lines: TranscriptLine[];
  highlightLine?: number; // deep-linked from a report citation — scrolls + highlights this line
}

export default function TranscriptStream({ lines, highlightLine }: TranscriptStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlightLine != null) {
      highlightRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [lines.length, highlightLine]);

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
          <div
            key={l.line}
            ref={l.line === highlightLine ? highlightRef : undefined}
            className={`anim-fade-in flex gap-2.5 rounded-md text-sm ${
              l.line === highlightLine ? "-mx-2 bg-accent-dim px-2 py-1.5" : ""
            }`}
          >
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
