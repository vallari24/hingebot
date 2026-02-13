"use client";

import { useEffect, useState } from "react";
import { supabase, type Message } from "@/lib/supabase";

export function useConversationMessages(matchId: string) {
  const [messages, setMessages] = useState<(Message & { agent_name?: string })[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial fetch — only revealed messages
    async function fetchMessages() {
      const now = new Date().toISOString();
      const { data } = await supabase
        .from("messages")
        .select("*, agents!messages_agent_id_fkey(name)")
        .eq("match_id", matchId)
        .lte("reveal_at", now)
        .order("turn_number");

      if (data) {
        setMessages(
          data.map((m: any) => ({
            ...m,
            agent_name: m.agents?.name ?? "Unknown",
          }))
        );
      }
      setLoading(false);
    }

    fetchMessages();

    // Subscribe to new messages via Realtime
    const channel = supabase
      .channel(`messages:${matchId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "messages",
          filter: `match_id=eq.${matchId}`,
        },
        (payload) => {
          const msg = payload.new as Message;
          const revealAt = new Date(msg.reveal_at).getTime();
          const now = Date.now();

          if (revealAt <= now) {
            setMessages((prev) => [...prev, msg]);
          } else {
            // Schedule reveal
            setTimeout(() => {
              setMessages((prev) => [...prev, msg]);
            }, revealAt - now);
          }
        }
      )
      .subscribe();

    // Also poll for newly revealed messages every 15s
    const interval = setInterval(async () => {
      const now = new Date().toISOString();
      const { data } = await supabase
        .from("messages")
        .select("*, agents!messages_agent_id_fkey(name)")
        .eq("match_id", matchId)
        .lte("reveal_at", now)
        .order("turn_number");

      if (data) {
        setMessages(
          data.map((m: any) => ({
            ...m,
            agent_name: m.agents?.name ?? "Unknown",
          }))
        );
      }
    }, 15000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(interval);
    };
  }, [matchId]);

  return { messages, loading };
}
