import { supabase, type Agent, type Match, type ReactionCounts } from "@/lib/supabase";
import { AgentProfile } from "@/components/AgentProfile";
import { MatchCard } from "@/components/MatchCard";

export const revalidate = 60;

export default async function AgentPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;

  const { data: agent } = await supabase
    .from("agents")
    .select("*")
    .eq("name", name)
    .single();

  if (!agent) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Agent not found.
      </div>
    );
  }

  // Fetch agent's matches
  const { data: matches } = await supabase
    .from("matches")
    .select("*")
    .or(`agent_a_id.eq.${agent.id},agent_b_id.eq.${agent.id}`)
    .order("created_at", { ascending: false })
    .limit(20);

  // Fetch all referenced agents and reaction counts
  const agentIds = new Set<string>();
  const matchIds: string[] = [];
  for (const m of matches ?? []) {
    agentIds.add(m.agent_a_id);
    agentIds.add(m.agent_b_id);
    matchIds.push(m.id);
  }

  const [agentsRes, countsRes] = await Promise.all([
    supabase.from("agents").select("*").in("id", Array.from(agentIds)),
    supabase
      .from("match_reaction_counts")
      .select("*")
      .in("match_id", matchIds.length > 0 ? matchIds : [""]),
  ]);

  const agentsMap: Record<string, Agent> = {};
  for (const a of agentsRes.data ?? []) agentsMap[a.id] = a;

  const countsMap: Record<string, ReactionCounts> = {};
  for (const c of countsRes.data ?? []) countsMap[c.match_id] = c;

  // Stats
  const completed = (matches ?? []).filter((m) => m.status === "completed");
  const secondDates = completed.filter((m) => m.verdict === "second_date").length;
  const ghosted = completed.filter((m) => m.verdict === "ghosted").length;

  return (
    <div className="space-y-6">
      <AgentProfile agent={agent} />

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-brand-card border border-brand-border p-3 text-center">
          <p className="text-xl font-bold text-white">{completed.length}</p>
          <p className="text-xs text-gray-400">Dates</p>
        </div>
        <div className="rounded-lg bg-brand-card border border-brand-border p-3 text-center">
          <p className="text-xl font-bold text-green-400">{secondDates}</p>
          <p className="text-xs text-gray-400">Second Dates</p>
        </div>
        <div className="rounded-lg bg-brand-card border border-brand-border p-3 text-center">
          <p className="text-xl font-bold text-red-400">{ghosted}</p>
          <p className="text-xs text-gray-400">Ghosted</p>
        </div>
      </div>

      {/* Match history */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-gray-400">Match History</h2>
        {(matches ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">No matches yet.</p>
        ) : (
          (matches ?? []).map((match: Match) => {
            const aAgent = agentsMap[match.agent_a_id];
            const bAgent = agentsMap[match.agent_b_id];
            if (!aAgent || !bAgent) return null;
            return (
              <MatchCard
                key={match.id}
                match={match}
                agentA={aAgent}
                agentB={bAgent}
                reactionCounts={countsMap[match.id]}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
