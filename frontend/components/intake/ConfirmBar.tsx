import Button from "@/components/ui/Button";

interface ConfirmBarProps {
  onBack: () => void;
  onConfirm: () => void;
  submitting: boolean;
}

export default function ConfirmBar({ onBack, onConfirm, submitting }: ConfirmBarProps) {
  return (
    <div className="sticky bottom-0 mt-8 flex items-center justify-between border-t border-border bg-bg/95 px-1 py-4 backdrop-blur-sm">
      <Button variant="ghost" onClick={onBack} disabled={submitting}>
        ← Back to docs
      </Button>
      <Button onClick={onConfirm} disabled={submitting}>
        {submitting ? "Submitting..." : "Confirm & start calls →"}
      </Button>
    </div>
  );
}
