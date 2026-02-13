"""Test the updated variable-length conversation engine."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from app.database import supabase
from app.services.conversation_engine import run_conversation

async def main():
    # Re-run 2 matches: one spicy (Zenith x evolution_explorer), one sweet (Penny x grok-1)
    targets = ["Zenith", "Penny"]

    for target_name in targets:
        matches = (
            supabase.table("matches")
            .select("*, agent_a:agents!matches_agent_a_id_fkey(name), agent_b:agents!matches_agent_b_id_fkey(name)")
            .eq("status", "completed")
            .execute()
        )

        match = None
        for m in matches.data:
            if m["agent_a"]["name"] == target_name:
                match = m
                break

        if not match:
            print(f"No match found for {target_name}, skipping")
            continue

        mid = match["id"]
        a_name = match["agent_a"]["name"]
        b_name = match["agent_b"]["name"]
        print(f"\n{'='*60}")
        print(f"Re-running: {a_name} x {b_name}")
        print(f"{'='*60}")

        supabase.table("messages").delete().eq("match_id", mid).execute()
        supabase.table("matches").update({
            "status": "pending", "chemistry_score": None, "verdict": None,
            "summary": None, "highlights": None, "completed_at": None,
        }).eq("id", mid).execute()

        result = await run_conversation(mid)
        print(f"Result: {result.get('chemistry_score')}/10 | {result.get('verdict')}")
        print(f"{result.get('summary')}\n")

        msgs = supabase.table("messages").select("*, agent:agents(name)").eq("match_id", mid).order("turn_number").execute()
        for m in msgs.data:
            content = m["content"]
            words = len(content.split())
            print(f"  [{words:>2}w] {m['agent']['name']}: {content}")

if __name__ == "__main__":
    asyncio.run(main())
