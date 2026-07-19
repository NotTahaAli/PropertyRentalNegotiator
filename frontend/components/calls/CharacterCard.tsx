import { CHARACTER_CARDS } from "@/lib/characterCards";
import type { Dealer } from "@/lib/types";

export default function CharacterCard({ dealer }: { dealer: Dealer }) {
  const card = CHARACTER_CARDS[dealer.persona];

  return (
    <div className="max-h-[70vh] overflow-y-auto rounded-xl border border-border bg-surface p-5">
      <p className="font-mono text-[10px] uppercase tracking-wide text-text-dim">
        Character card
      </p>
      <h3 className="mt-1 font-display text-base font-semibold text-text">
        {card.title}
      </h3>
      <ul className="mt-4 flex flex-col gap-3">
        {card.bullets.map((b, i) => (
          <li key={i} className="text-sm leading-relaxed text-text-secondary">
            {b}
          </li>
        ))}
      </ul>
    </div>
  );
}
