"use client";

import { useEffect, useState } from "react";
import { getSpec } from "./api";

// Human-readable spec label for nav breadcrumbs — same "location, else
// Untitled spec" fallback SpecCard uses on the dashboard. Falls back to the
// raw id while loading/on error rather than blocking the breadcrumb.
export function useSpecLabel(specId: string): string {
  const [label, setLabel] = useState(specId);
  // reset synchronously during render when specId changes, so switching
  // between two specs under the same mounted layout never flashes the
  // previous spec's label (see react.dev "adjusting state on prop change")
  const [trackedId, setTrackedId] = useState(specId);
  if (specId !== trackedId) {
    setTrackedId(specId);
    setLabel(specId);
  }

  useEffect(() => {
    let cancelled = false;
    getSpec(specId)
      .then((s) => !cancelled && setLabel(s.spec.location || "Untitled spec"))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [specId]);

  return label;
}
