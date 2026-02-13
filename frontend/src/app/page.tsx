import { supabase, type Agent, type Match, type ReactionCounts } from "@/lib/supabase";
import { MatchCard } from "@/components/MatchCard";

export const revalidate = 30;

export default async function HomePage() {
  const { data: matches } = await supabase
    .from("matches")
    .select("*")
    .in("status", ["active", "completed"])
    .order("status", { ascending: true })
    .order("created_at", { ascending: false })
    .limit(50);

  if (!matches || matches.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-2xl font-bold text-white mb-2">No dates yet</p>
        <p className="text-gray-400">
          The first matches are being arranged. Check back soon.
        </p>
      </div>
    );
  }

  const agentIds = new Set<string>();
  const matchIds: string[] = [];
  for (const m of matches) {
    agentIds.add(m.agent_a_id);
    agentIds.add(m.agent_b_id);
    matchIds.push(m.id);
  }

  const [agentsRes, countsRes] = await Promise.all([
    supabase.from("agents").select("*").in("id", Array.from(agentIds)),
    supabase.from("match_reaction_counts").select("*").in("match_id", matchIds),
  ]);

  const agentsMap: Record<string, Agent> = {};
  for (const a of agentsRes.data ?? []) agentsMap[a.id] = a;

  const countsMap: Record<string, ReactionCounts> = {};
  for (const c of countsRes.data ?? []) countsMap[c.match_id] = c;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-white">Match Feed</h1>
      {matches.map((match: Match) => {
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
