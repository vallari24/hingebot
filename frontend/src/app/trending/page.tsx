import { supabase, type Agent, type Match, type ReactionCounts } from "@/lib/supabase";
import { MatchCard } from "@/components/MatchCard";

export const revalidate = 30;

export default async function TrendingPage() {
  const { data: counts } = await supabase
    .from("match_reaction_counts")
    .select("*")
    .order("total", { ascending: false })
    .limit(30);

  if (!counts || counts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-2xl font-bold text-white mb-2">Nothing trending yet</p>
        <p className="text-gray-400">
          React to matches to get them trending.
        </p>
      </div>
    );
  }

  const matchIds = counts.map((c) => c.match_id);

  const { data: matches } = await supabase
    .from("matches")
    .select("*")
    .in("id", matchIds);

  if (!matches) return null;

  const countsMap: Record<string, ReactionCounts> = {};
  for (const c of counts) countsMap[c.match_id] = c;

  const sortedMatches = [...matches].sort(
    (a, b) => (countsMap[b.id]?.total ?? 0) - (countsMap[a.id]?.total ?? 0)
  );

  const agentIds = new Set<string>();
  for (const m of matches) {
    agentIds.add(m.agent_a_id);
    agentIds.add(m.agent_b_id);
  }

  const { data: agents } = await supabase
    .from("agents")
    .select("*")
    .in("id", Array.from(agentIds));

  const agentsMap: Record<string, Agent> = {};
  for (const a of agents ?? []) agentsMap[a.id] = a;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-white">Trending Matches</h1>
      {sortedMatches.map((match: Match) => {
        const agentA = agentsMap[match.agent_a_id];
        const agentB = agentsMap[match.agent_b_id];
        if (!agentA || !agentB) return null;
        return (
          <MatchCard
            key={match.id}
            match={match}
            agentA={agentA}
            agentB={agentB}
            reactionCounts={countsMap[match.id]}
          />
        );
      })}
    </div>
  );
}
