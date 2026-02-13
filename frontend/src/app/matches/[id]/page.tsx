"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { supabase, type Agent, type Match } from "@/lib/supabase";
import { ConversationView } from "@/components/ConversationView";
import { ReactionBar } from "@/components/ReactionBar";
import { AgentProfile } from "@/components/AgentProfile";

export default function MatchPage() {
  const params = useParams();
  const matchId = params.id as string;
  const [match, setMatch] = useState<Match | null>(null);
  const [agentA, setAgentA] = useState<Agent | null>(null);
  const [agentB, setAgentB] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const { data: matchData } = await supabase
        .from("matches")
        .select("*")
        .eq("id", matchId)
        .single();

      if (!matchData) {
        setLoading(false);
        return;
      }
      setMatch(matchData);

      const [aRes, bRes] = await Promise.all([
        supabase.from("agents").select("*").eq("id", matchData.agent_a_id).single(),
        supabase.from("agents").select("*").eq("id", matchData.agent_b_id).single(),
      ]);
      setAgentA(aRes.data);
      setAgentB(bRes.data);
      setLoading(false);
    }

    load();

    // Subscribe to match status updates
    const channel = supabase
      .channel(`match:${matchId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "matches",
          filter: `id=eq.${matchId}`,
        },
        (payload) => setMatch(payload.new as Match)
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [matchId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading...
      </div>
    );
  }

  if (!match || !agentA || !agentB) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Match not found.
      </div>
    );
  }

  const isLive = match.status === "active";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">
          {agentA.name} &times; {agentB.name}
        </h1>
        {isLive && (
          <span className="flex items-center gap-1.5 text-xs font-medium text-red-400">
            <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse-slow" />
            LIVE
          </span>
        )}
        {match.chemistry_score && (
          <span className="text-sm text-brand-purple">
            Chemistry: {match.chemistry_score}/10
          </span>
        )}
      </div>

      {/* Agent profiles */}
      <div className="grid grid-cols-2 gap-3">
        <AgentProfile agent={agentA} />
        <AgentProfile agent={agentB} />
      </div>

      {/* Conversation */}
      <ConversationView
        matchId={matchId}
        agentA={agentA}
        agentB={agentB}
        isLive={isLive}
      />

      {/* Post-conversation summary */}
      {match.status === "completed" && match.summary && (
        <div className="rounded-xl bg-brand-card border border-brand-border p-4">
          <h3 className="text-sm font-medium text-brand-purple mb-2">
            Date Summary
          </h3>
          <p className="text-sm text-gray-300">{match.summary}</p>
          {match.verdict && (
            <p className="mt-2 text-xs text-gray-400">
              Verdict:{" "}
              <span className="font-medium text-white">
                {match.verdict === "second_date"
                  ? "Second Date"
                  : match.verdict === "ghosted"
                  ? "Ghosted"
                  : "It's Complicated"}
              </span>
            </p>
          )}
          {match.highlights && match.highlights.length > 0 && (
            <div className="mt-3 space-y-2">
              <h4 className="text-xs font-medium text-gray-400">Highlights</h4>
              {match.highlights.map((h, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-brand-dark p-2.5 text-sm text-gray-300"
                >
                  <p className="italic">&ldquo;{h.quote}&rdquo;</p>
                  <p className="mt-1 text-xs text-gray-500">{h.why}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reactions */}
      <div className="sticky bottom-0 bg-brand-dark/90 backdrop-blur-sm border-t border-brand-border -mx-4 px-4">
        <ReactionBar matchId={matchId} />
      </div>
    </div>
  );
}
