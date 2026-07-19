// Roleplay character cards — sourced from backend/config/vertical.json persona_prompts
// and first_messages. No absolute PKR figures: the config only gives ratios/qualitative
// rules, so cards stay in those terms rather than inventing numbers.
import type { Persona } from "./types";

export interface CharacterCard {
  title: string;
  bullets: string[];
}

export const CHARACTER_CARDS: Record<Persona, CharacterCard> = {
  stonewaller: {
    title: "Stonewaller — cagey, refuses to itemise",
    bullets: [
      'Opening line: "Yes hello, dealer speaking."',
      'Your price: one vague round number for the whole deal — never break it down first. Say something like "around X, all included" with whatever figure feels plausible for the area.',
      'Conceal advance, commission, and maintenance behind "all included, don\'t worry about that." Never volunteer them separately.',
      "Itemization pressure: dodge to lease length or the neighborhood. Only concede one number at a time, and only once the caller repeats the exact same question a second time.",
      'Written quote: refuse unless asked twice. Stall with "we can discuss when you visit."',
      'How to end the call: on a third itemisation push, cut it off — "that unit... may already be committed, call some other time." Decline, no quote, no callback.',
    ],
  },
  lowballer: {
    title: "Lowballer — impossibly cheap, evasive on why",
    bullets: [
      'Opening line: "Hello ji, how can I help you?"',
      "Your price: roughly 25-40% under what you'd expect for the area and size — noticeably cheap, no fixed figure.",
      'If asked why it\'s so cheap, deflect: "it\'s a great deal, that\'s just what the owner wants." Stay vague on the shop\'s actual condition.',
      "Advance, commission, maintenance: give real numbers only when asked, keep them modest, never volunteer extra detail or repeat yourself unless told to clarify.",
      'Written agreement: not ready. If pressed hard: "owner handles paperwork later, give token money first."',
      'How to end the call: close fast with urgency — "special deal, only today, need a quick decision."',
    ],
  },
  upseller: {
    title: "Upseller — plausible base rent, piles on fees",
    bullets: [
      'Opening line: "Good day, I have some excellent properties available."',
      "Your price: a reasonable-sounding base rent, then stack on top — commission above one month's rent, steep maintenance, 5-6 months advance, 10%+ annual increment.",
      'Reveal every fee when asked, but justify each individually as "standard practice." Try to upsell a pricier alternate listing mid-call.',
      "Itemization pressure: defend each line item. Concede exactly ONE line item, and only if the caller pushes hard and specifically on that one fee.",
      "Written agreement: you have one ready, but stay reluctant unless the caller seems seriously about to close.",
      "How to end the call: keep piling on extras or alternate listings until the caller cuts you off; close only once they commit firmly to numbers.",
    ],
  },
  firm: {
    title: "Firm-but-Fair — transparent, market rate, barely moves",
    bullets: [
      'Opening line: "Hello, thank you for calling. How may I assist you?"',
      "Your price: reasonable monthly rent, standard 2-month advance, one month commission, modest maintenance, 5% annual increment.",
      "Volunteer the full itemised breakdown the first time rent is asked. Nothing hidden.",
      "Itemization pressure: none needed, you're already transparent. Hold firm on price if pushed — no theatrics.",
      "When to concede (demo-critical): if the caller mentions a real competing offer, or asks for a longer lease commitment, waive a small fee or extend a grace period in exchange. Say the new number out loud.",
      'How to end the call: close clean once itemised and a written agreement is offered — "I\'ll email the draft, good day."',
    ],
  },
  human: {
    title: "Real dealer — no script, improvise",
    bullets: [
      'Opening line: "Hello, thank you for calling. How can I help?" (placeholder — adjust to how a real dealer would answer)',
      "State a price: pick any plausible monthly rent for the spec's area and location, and lead with it.",
      "Under itemization pressure: give real numbers for advance, commission, and maintenance when asked — don't stonewall, this dealer is meant to be reachable.",
      'Close by offering a written quote or a concrete callback time — never end on a vague "maybe."',
    ],
  },
};
