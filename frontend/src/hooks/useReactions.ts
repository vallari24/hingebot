"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase, type ReactionCounts, type ReactionType } from "@/lib/supabase";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = sessionStorage.getItem("hingebot_session");
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem("hingebot_session", id);
  }
  return id;
}

export function useReactions(matchId: string) {
  const [counts, setCounts] = useState<ReactionCounts>({
    match_id: matchId,
    fire: 0,
    cringe: 0,
    wholesome: 0,
    chaotic: 0,
    ship_it: 0,
    total: 0,
  });
  const [myReactions, setMyReactions] = useState<Set<ReactionType>>(new Set());

  useEffect(() => {
    // Fetch initial counts
    async function fetchCounts() {
      const { data } = await supabase
        .from("match_reaction_counts")
        .select("*")
        .eq("match_id", matchId)
        .single();

      if (data) setCounts(data);
    }

    // Fetch my reactions
    async function fetchMyReactions() {
      const sessionId = getSessionId();
      if (!sessionId) return;
      const { data } = await supabase
        .from("reactions")
        .select("reaction_type")
        .eq("match_id", matchId)
        .eq("session_id", sessionId);

      if (data) {
        setMyReactions(new Set(data.map((r: any) => r.reaction_type)));
      }
    }

    fetchCounts();
    fetchMyReactions();

    // Subscribe to count updates
    const channel = supabase
      .channel(`reaction_counts:${matchId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "match_reaction_counts",
          filter: `match_id=eq.${matchId}`,
        },
        (payload) => {
          if (payload.new) setCounts(payload.new as ReactionCounts);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [matchId]);

  const react = useCallback(
    async (reactionType: ReactionType) => {
      const sessionId = getSessionId();
      if (myReactions.has(reactionType)) return;

      const { error } = await supabase.from("reactions").insert({
        match_id: matchId,
        reaction_type: reactionType,
        session_id: sessionId,
      });

      if (!error) {
        setMyReactions((prev) => new Set([...Array.from(prev), reactionType]));
        setCounts((prev) => ({
          ...prev,
          [reactionType]: prev[reactionType] + 1,
          total: prev.total + 1,
        }));
      }
    },
    [matchId, myReactions]
  );

  return { counts, myReactions, react };
}
