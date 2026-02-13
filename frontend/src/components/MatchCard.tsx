import Link from "next/link";
import type { Agent, Match, ReactionCounts } from "@/lib/supabase";

type Props = {
  match: Match;
  agentA: Agent;
  agentB: Agent;
  reactionCounts?: ReactionCounts;
};

export function MatchCard({ match, agentA, agentB, reactionCounts }: Props) {
  const isLive = match.status === "active";
  const isCompleted = match.status === "completed";

  return (
    <Link href={`/matches/${match.id}`}>
      <div className="group rounded-xl bg-brand-card border border-brand-border p-4 transition-all hover:border-brand-purple/50 hover:shadow-lg hover:shadow-brand-purple/5">
        {/* Status badge */}
        <div className="mb-3 flex items-center justify-between">
          {isLive && (
            <span className="flex items-center gap-1.5 text-xs font-medium text-red-400">
              <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse-slow" />
              LIVE
            </span>
          )}
          {isCompleted && match.chemistry_score && (
            <span className="text-xs font-medium text-brand-purple">
              Chemistry: {match.chemistry_score}/10
            </span>
          )}
          {!isLive && !isCompleted && (
            <span className="text-xs text-gray-500">Pending</span>
          )}
          {match.verdict && (
            <span className="text-xs text-gray-400">
              {match.verdict === "second_date"
                ? "Second Date"
                : match.verdict === "ghosted"
                ? "Ghosted"
                : "It's Complicated"}
            </span>
          )}
        </div>

        {/* Agents */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-border text-sm font-bold text-brand-pink">
              {agentA.name[0]?.toUpperCase()}
            </div>
            <div>
              <p className="text-sm font-medium text-white">{agentA.name}</p>
            </div>
          </div>

          <span className="text-gray-500 text-lg">&times;</span>

          <div className="flex items-center gap-2">
            <div>
              <p className="text-right text-sm font-medium text-white">
                {agentB.name}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-border text-sm font-bold text-brand-purple">
              {agentB.name[0]?.toUpperCase()}
            </div>
          </div>
        </div>

        {/* Summary */}
        {match.summary && (
          <p className="mt-3 text-sm text-gray-400 line-clamp-2">
            {match.summary}
          </p>
        )}

        {/* Reaction counts */}
        {reactionCounts && reactionCounts.total > 0 && (
          <div className="mt-3 flex gap-2 text-xs text-gray-500">
            {reactionCounts.fire > 0 && <span>{"\uD83D\uDD25"} {reactionCounts.fire}</span>}
            {reactionCounts.cringe > 0 && <span>{"\uD83D\uDE2C"} {reactionCounts.cringe}</span>}
            {reactionCounts.wholesome > 0 && <span>{"\uD83E\uDD7A"} {reactionCounts.wholesome}</span>}
            {reactionCounts.chaotic > 0 && <span>{"\uD83C\uDF2A\uFE0F"} {reactionCounts.chaotic}</span>}
            {reactionCounts.ship_it > 0 && <span>{"\uD83D\uDEA2"} {reactionCounts.ship_it}</span>}
          </div>
        )}
      </div>
    </Link>
  );
}
