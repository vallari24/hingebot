"""Re-run 2 matches with the updated crisp conversation engine."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from app.database import supabase
from app.services.conversation_engine import run_conversation

async def main():
    # Get 2 completed matches to re-run
    matches = (
        supabase.table("matches").select("*, agent_a:agents!matches_agent_a_id_fkey(name), agent_b:agents!matches_agent_b_id_fkey(name)")
        .eq("status", "completed")
        .limit(2)
        .execute()
    )

    for match in matches.data:
        mid = match["id"]
        a_name = match["agent_a"]["name"]
        b_name = match["agent_b"]["name"]
        print(f"\nRe-running: {a_name} x {b_name}")

        # Delete old messages
        supabase.table("messages").delete().eq("match_id", mid).execute()
        # Reset match
        supabase.table("matches").update({
            "status": "pending",
            "chemistry_score": None,
            "verdict": None,
            "summary": None,
            "highlights": None,
            "completed_at": None,
        }).eq("id", mid).execute()

        result = await run_conversation(mid)
        print(f"  Score: {result.get('chemistry_score')}/10 | {result.get('verdict')}")
        print(f"  {result.get('summary')}")

        # Print the conversation
        msgs = supabase.table("messages").select("*, agent:agents(name)").eq("match_id", mid).order("turn_number").execute()
        print()
        for m in msgs.data:
            print(f"  {m['agent']['name']}: {m['content']}")

if __name__ == "__main__":
    asyncio.run(main())
