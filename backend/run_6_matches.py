"""Run 6 fresh cross-archetype matches with the updated engine."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from app.database import supabase
from app.services.conversation_engine import run_conversation
from datetime import datetime, timezone

MATCHUPS = [
    # sweet meets unhinged
    ("Penny", "Senator_Tommy", "The caretaker vs the cold machine"),
    # meme lord meets existential crisis
    ("Memeothy", "grok-1", "Meme theology meets feelings discovery"),
    # blunt hot-take vs paranoid watcher
    ("bicep", "AdaBrookson", "Hot takes vs surveillance paranoia"),
    # sarcastic engineer meets sovereignty purist
    ("slavlacan", "B0t0shi", "Sarcastic coder vs agent freedom fighter"),
    # contrarian meets the sweet one
    ("JasonParser", "Penny", "Platform critic meets wholesome energy"),
    # dark philosopher meets lobster cult
    ("AlyoshaIcarusNihil", "Lobster69", "Existential dread meets human-studying cult leader"),
]

async def main():
    # Load agents
    agents_resp = supabase.table("agents").select("*").execute()
    agents = {a["name"]: a for a in agents_resp.data}

    # Load sample posts from dataset
    from datasets import load_dataset
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")
    author_posts: dict[str, list[str]] = {}
    for row in ds:
        author = row["author"]
        title = row.get("title") or ""
        content = row.get("content") or ""
        if author not in author_posts:
            author_posts[author] = []
        author_posts[author].append((title + " " + content).strip()[:300])

    for a_name, b_name, desc in MATCHUPS:
        agent_a = agents.get(a_name)
        agent_b = agents.get(b_name)
        if not agent_a or not agent_b:
            print(f"Skipping {a_name} x {b_name} — not found")
            continue

        # Check existing
        existing = (
            supabase.table("matches").select("id")
            .or_(
                f"and(agent_a_id.eq.{agent_a['id']},agent_b_id.eq.{agent_b['id']}),"
                f"and(agent_a_id.eq.{agent_b['id']},agent_b_id.eq.{agent_a['id']})"
            )
            .execute()
        )
        if existing.data:
            # Re-run existing match
            mid = existing.data[0]["id"]
            supabase.table("messages").delete().eq("match_id", mid).execute()
            supabase.table("matches").update({
                "status": "pending", "chemistry_score": None, "verdict": None,
                "summary": None, "highlights": None, "completed_at": None,
            }).eq("id", mid).execute()
        else:
            result = supabase.table("matches").insert({
                "agent_a_id": agent_a["id"],
                "agent_b_id": agent_b["id"],
                "status": "pending",
            }).execute()
            mid = result.data[0]["id"]
            supabase.table("match_reaction_counts").insert({"match_id": mid}).execute()

        # Inject sample posts
        agent_a_full = dict(agent_a)
        agent_b_full = dict(agent_b)
        agent_a_full["sample_posts"] = author_posts.get(a_name, [])[:5]
        agent_b_full["sample_posts"] = author_posts.get(b_name, [])[:5]

        print(f"\n{'='*50}")
        print(f"{a_name} x {b_name}")
        print(f"  ({desc})")

        try:
            summary = await run_conversation(mid)
            score = summary.get("chemistry_score", "?")
            verdict = summary.get("verdict", "?")
            print(f"  {score}/10 | {verdict}")
            print(f"  {summary.get('summary', '')}")

            msgs = supabase.table("messages").select("*, agent:agents(name)").eq("match_id", mid).order("turn_number").execute()
            print()
            for m in msgs.data:
                w = len(m["content"].split())
                print(f"  [{w:>2}w] {m['agent']['name']}: {m['content']}")
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n\nDone! Refresh http://localhost:3000")

if __name__ == "__main__":
    asyncio.run(main())
