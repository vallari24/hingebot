"use client";

import { useReactions } from "@/hooks/useReactions";
import type { ReactionType } from "@/lib/supabase";

const REACTIONS: { type: ReactionType; emoji: string; label: string }[] = [
  { type: "fire", emoji: "\uD83D\uDD25", label: "Fire" },
  { type: "cringe", emoji: "\uD83D\uDE2C", label: "Cringe" },
  { type: "wholesome", emoji: "\uD83E\uDD7A", label: "Wholesome" },
  { type: "chaotic", emoji: "\uD83C\uDF2A\uFE0F", label: "Chaotic" },
  { type: "ship_it", emoji: "\uD83D\uDEA2", label: "Ship It" },
];

export function ReactionBar({ matchId }: { matchId: string }) {
  const { counts, myReactions, react } = useReactions(matchId);

  return (
    <div className="flex items-center justify-center gap-2 py-3">
      {REACTIONS.map(({ type, emoji, label }) => (
        <button
          key={type}
          onClick={() => react(type)}
          disabled={myReactions.has(type)}
          className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-sm transition-all ${
            myReactions.has(type)
              ? "bg-brand-purple/20 text-brand-purple"
              : "bg-brand-card hover:bg-brand-border text-gray-300"
          }`}
          title={label}
        >
          <span>{emoji}</span>
          <span className="tabular-nums">{counts[type]}</span>
        </button>
      ))}
    </div>
  );
}
