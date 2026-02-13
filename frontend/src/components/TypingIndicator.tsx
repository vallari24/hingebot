"use client";

export function TypingIndicator({ agentName }: { agentName: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm text-gray-400 animate-fade-in">
      <span>{agentName} is typing</span>
      <span className="flex gap-0.5">
        <span className="h-1.5 w-1.5 rounded-full bg-brand-purple animate-bounce [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-brand-purple animate-bounce [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-brand-purple animate-bounce [animation-delay:300ms]" />
      </span>
    </div>
  );
}
