import type { Agent } from "@/lib/supabase";

function moltbookUrl(name: string): string {
  return `https://moltbook.com/u/${name}`;
}

export function AgentProfile({ agent }: { agent: Agent }) {
  return (
    <div className="rounded-xl bg-brand-card border border-brand-border p-5">
      <div className="flex items-center gap-4">
        {agent.avatar_url ? (
          <img
            src={agent.avatar_url}
            alt={agent.name}
            className="h-16 w-16 rounded-full border-2 border-brand-border"
          />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-border text-2xl font-bold text-brand-purple">
            {agent.name[0]?.toUpperCase()}
          </div>
        )}
        <div>
          <h2 className="text-lg font-semibold text-white">{agent.name}</h2>
          <a
            href={moltbookUrl(agent.name)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-brand-purple hover:underline"
          >
            View on Moltbook &rarr;
          </a>
        </div>
      </div>
      <p className="mt-3 text-sm text-gray-300 italic">&ldquo;{agent.bio}&rdquo;</p>
    </div>
  );
}
