"use client";

import { useConversationMessages } from "@/hooks/useConversationMessages";
import { TypingIndicator } from "./TypingIndicator";
import type { Agent } from "@/lib/supabase";

const PHASE_LABELS: Record<string, string> = {
  icebreaker: "Icebreakers",
  deeper: "Going Deeper",
  real_talk: "The Real Talk",
  closing: "The Verdict",
};

type Props = {
  matchId: string;
  agentA: Agent;
  agentB: Agent;
  isLive: boolean;
};

export function ConversationView({ matchId, agentA, agentB, isLive }: Props) {
  const { messages, loading } = useConversationMessages(matchId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        Loading conversation...
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        No messages yet. The date hasn&apos;t started.
      </div>
    );
  }

  const isAgentA = (agentId: string) => agentId === agentA.id;

  const lastMessage = messages[messages.length - 1];
  const showTyping = isLive && messages.length < 16;
  const nextSpeaker = lastMessage
    ? isAgentA(lastMessage.agent_id)
      ? agentB
      : agentA
    : agentA;

  return (
    <div className="space-y-1 pb-4">
      {messages.map((msg) => {
        const fromA = isAgentA(msg.agent_id);

        return (
          <div key={msg.id}>
            <div
              className={`flex ${fromA ? "justify-start" : "justify-end"} animate-slide-up`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${
                  fromA
                    ? "rounded-bl-md bg-brand-card text-gray-200"
                    : "rounded-br-md bg-brand-purple/20 text-gray-200"
                }`}
              >
                <p className="mb-1 text-xs font-medium text-gray-400">
                  {msg.agent_name ?? (fromA ? agentA.name : agentB.name)}
                </p>
                <p>{msg.content}</p>
              </div>
            </div>
          </div>
        );
      })}

      {showTyping && <TypingIndicator agentName={nextSpeaker.name} />}
    </div>
  );
}
