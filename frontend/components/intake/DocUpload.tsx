"use client";

import { useState, useRef, DragEvent } from "react";
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
}

function UploadSlot({ label, kind, onParsed }: SlotProps) {
  const [state, setState] = useState<SlotState>({ status: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!ACCEPTED_MIME.includes(file.type)) {
      setState({ status: "error", fileName: file.name, message: "Unsupported file type" });
      return;
    }
    if (file.size > MAX_BYTES) {
      setState({ status: "error", fileName: file.name, message: "File too large (max 10 MB)" });
      return;
    }
    setState({ status: "loading", fileName: file.name });
    try {
      const parsed = await parseDoc(file, kind);
      onParsed(parsed);
      setState({
        status: "done",
        fileName: file.name,
        fieldCount: Object.keys(parsed.partial_spec).length,
      });
    } catch {
      setState({ status: "error", fileName: file.name, message: "Parse failed" });
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <div
      className="rounded-lg border border-dashed border-line bg-panel p-5"
      onDragOver={(e) => e.preventDefault()}
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
      <p className="mb-2 font-mono text-xs uppercase tracking-wide text-muted">{label}</p>

      {state.status === "idle" && (
        <p className="text-sm text-muted">Drag & drop, or click to browse</p>
      )}
      {state.status === "loading" && (
        <p className="text-sm text-blue">Parsing {state.fileName}...</p>
      )}
      {state.status === "done" && (
        <p className="text-sm text-green">
          ✓ {state.fileName} — {state.fieldCount} fields extracted
        </p>
      )}
      {state.status === "error" && (
        <div className="text-sm text-red">
          {state.message} ({state.fileName}).{" "}
          <button
            className="underline"
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
}: {
  onParsed: (parsed: ParsedDoc) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <UploadSlot label="Rent Agreement (PDF/Image)" kind="rent_agreement" onParsed={onParsed} />
      <UploadSlot
        label="Requirements Doc (PDF/Image/DOCX)"
        kind="requirements"
        onParsed={onParsed}
      />
    </div>
  );
}
