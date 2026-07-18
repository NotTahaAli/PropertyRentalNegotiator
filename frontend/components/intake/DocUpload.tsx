"use client";

import { useState, useRef, DragEvent, useEffect } from "react";
import { parseDoc } from "@/lib/api";
import type { ParsedDoc } from "@/lib/types";

const ACCEPTED_MIME = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const MAX_BYTES = 10 * 1024 * 1024;

type SlotState =
  | { status: "idle" }
  | { status: "loading"; fileName: string }
  | { status: "done"; fileName: string; fieldCount: number }
  | { status: "error"; fileName: string; message: string };

interface SlotProps {
  label: string;
  kind: ParsedDoc["kind"];
  onParsed: (parsed: ParsedDoc) => void;
  onDone: (isDone: boolean) => void;
  onParseFailed?: () => void;
}

function UploadSlot({ label, kind, onParsed, onDone, onParseFailed }: SlotProps) {
  const [state, setState] = useState<SlotState>({ status: "idle" });
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!ACCEPTED_MIME.includes(file.type)) {
      setState({ status: "error", fileName: file.name, message: "Unsupported file type" });
      onDone(false);
      return;
    }
    if (file.size > MAX_BYTES) {
      setState({ status: "error", fileName: file.name, message: "File too large (max 10 MB)" });
      onDone(false);
      return;
    }
    setState({ status: "loading", fileName: file.name });
    onDone(false);
    try {
      const parsed = await parseDoc(file, kind);
      onParsed(parsed);
      setState({
        status: "done",
        fileName: file.name,
        fieldCount: Object.keys(parsed.partial_spec).length,
      });
      onDone(true);
    } catch {
      setState({ status: "error", fileName: file.name, message: "Parse failed" });
      onDone(false);
      onParseFailed?.();
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  const isDone = state.status === "done";

  return (
    <div
      className={`tr group cursor-pointer rounded-xl border-2 border-dashed p-6 sm:p-8 ${
        dragOver
          ? "border-accent/50 bg-accent-dim"
          : isDone
            ? "border-success/30 bg-success-dim"
            : "border-border hover:border-border-hover hover:bg-surface"
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={ACCEPTED_MIME.join(",")}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {/* upload icon */}
      <div className={`tr mb-3 inline-flex rounded-lg border p-2.5 ${
        isDone
          ? "border-success/20 bg-success/10 text-success"
          : "border-border bg-elevated text-text-dim group-hover:text-text-secondary"
      }`}>
        {isDone ? (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M4 10L8.5 14.5L16 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 14V4m0 0L6 8m4-4l4 4M3 17h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>

      <p className="font-display text-sm font-semibold text-text">{label}</p>

      {state.status === "idle" && (
        <p className="mt-1 text-sm text-text-dim">
          Drag & drop or <span className="text-text-secondary underline underline-offset-2">browse files</span>
        </p>
      )}
      {state.status === "loading" && (
        <p className="mt-1 text-sm text-info">Parsing {state.fileName}...</p>
      )}
      {state.status === "done" && (
        <p className="mt-1 text-sm text-success">
          ✓ {state.fieldCount} fields extracted from {state.fileName}
        </p>
      )}
      {state.status === "error" && (
        <div className="mt-1 text-sm text-error">
          {state.message} ({state.fileName}).{" "}
          <button
            className="underline underline-offset-2"
            onClick={(e) => {
              e.stopPropagation();
              setState({ status: "idle" });
            }}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

export default function DocUpload({
  onParsed,
  onCompletionChange,
  onParseFailed,
}: {
  onParsed: (parsed: ParsedDoc) => void;
  onCompletionChange?: (isComplete: boolean) => void;
  onParseFailed?: () => void;
}) {
  const [rentDone, setRentDone] = useState(false);
  const [reqDone, setReqDone] = useState(false);

  useEffect(() => {
    onCompletionChange?.(rentDone && reqDone);
  }, [rentDone, reqDone, onCompletionChange]);

  return (
    <div className="step-enter grid gap-4 sm:grid-cols-2">
      <UploadSlot label="Rent agreement" kind="rent_agreement" onParsed={onParsed} onDone={setRentDone} onParseFailed={onParseFailed} />
      <UploadSlot label="Requirements document" kind="requirements" onParsed={onParsed} onDone={setReqDone} onParseFailed={onParseFailed} />
    </div>
  );
}
