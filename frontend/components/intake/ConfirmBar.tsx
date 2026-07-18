import Button from "@/components/ui/Button";

interface ConfirmBarProps {
  onBack: () => void;
  onConfirm: () => void;
  submitting: boolean;
}

export default function ConfirmBar({ onBack, onConfirm, submitting }: ConfirmBarProps) {
  return (
    <div className="sticky bottom-0 mt-6 flex items-center justify-between border-t border-line bg-ink/95 px-1 py-4 shadow-[0_-8px_20px_-12px_rgba(0,0,0,0.6)]">
      <Button variant="ghost" onClick={onBack} disabled={submitting}>
        ← Back to docs
      </Button>
      <Button onClick={onConfirm} disabled={submitting}>
        {submitting ? "Submitting..." : "Confirm & Start Calls →"}
      </Button>
    </div>
  );
}
