import Link from "next/link";

interface CitationLinkProps {
  specId: string;
  callNumber: number;
  line: number;
  className?: string;
}

// Deep-links into K9's transcript view — /calls/[spec_id] reads ?call=&line=
// on load and scrolls/highlights the matching line.
export default function CitationLink({ specId, callNumber, line, className = "" }: CitationLinkProps) {
  return (
    <Link
      href={`/calls/${encodeURIComponent(specId)}?call=${callNumber}&line=${line}`}
      className={`tr font-mono text-[11px] text-accent hover:opacity-75 ${className}`}
    >
      [call {callNumber}, line {line}]
    </Link>
  );
}
