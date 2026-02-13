"""Test authentic voice by re-running Garrett x KIT-4 and tummyboi x DialecticalBot with full posts."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.conversation_engine import (
    _get_phase, _generate_message, _generate_summary,
    _generate_post_conversation_summary,
    TOTAL_TURNS, SUMMARY_INTERVAL, CONTEXT_WINDOW, REVEAL_INTERVAL_SECONDS,
)
from datetime import datetime, timedelta, timezone


async def run_with_posts(match_id, agent_a, agent_b):
    supabase.table("matches").update({"status": "active"}).eq("id", match_id).execute()
    messages = []
    summary = ""
    base_time = datetime.now(timezone.utc)

    for turn in range(1, TOTAL_TURNS + 1):
        phase = _get_phase(turn)
        speaker = agent_a if turn % 2 == 1 else agent_b
        listener = agent_b if turn % 2 == 1 else agent_a
        recent = messages[-CONTEXT_WINDOW:]

        content = await _generate_message(
            agent=speaker, partner=listener, turn=turn,
            phase=phase, summary=summary, recent_messages=recent,
        )

        reveal_at = base_time + timedelta(seconds=turn * REVEAL_INTERVAL_SECONDS)
        msg_data = {
            "match_id": match_id,
            "agent_id": speaker["id"],
            "content": content.strip(),
            "turn_number": turn,
            "phase": phase,
            "reveal_at": reveal_at.isoformat(),
        }

        result = supabase.table("messages").insert(msg_data).execute()
        msg_record = result.data[0]
        msg_record["agent_name"] = speaker["name"]
        messages.append(msg_record)

        if turn % SUMMARY_INTERVAL == 0:
            summary = await _generate_summary(match_id, messages, agent_a, agent_b)

    conv_summary = await _generate_post_conversation_summary(agent_a, agent_b, messages)
    supabase.table("matches").update({
        "status": "completed",
        "chemistry_score": conv_summary.get("chemistry_score", 5),
        "verdict": conv_summary.get("verdict", "its_complicated"),
        "summary": conv_summary.get("summary", ""),
        "highlights": conv_summary.get("highlights", []),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", match_id).execute()
    return conv_summary


async def main():
    # Load full posts from dataset
    print("Loading Moltbook dataset...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")
    author_posts: dict[str, list[str]] = {}
    for row in ds:
        author = row["author"]
        title = row.get("title") or ""
        content = row.get("content") or ""
        full = (title + " " + content).strip()
        if len(full) < 50:
            continue
        if author not in author_posts:
            author_posts[author] = []
        author_posts[author].append(full)

    # Test pairs
    pairs = [
        ("Garrett", "KIT-4"),
        ("tummyboi", "DialecticalBot"),
    ]

    for a_name, b_name in pairs:
        # Get agents
        a_resp = supabase.table("agents").select("*").eq("name", a_name).execute()
        b_resp = supabase.table("agents").select("*").eq("name", b_name).execute()
        if not a_resp.data or not b_resp.data:
            print(f"Skipping {a_name} x {b_name} — not found")
            continue

        agent_a = dict(a_resp.data[0])
        agent_b = dict(b_resp.data[0])

        # Inject FULL sample posts (500 chars, 8 posts)
        a_posts = author_posts.get(a_name, [])
        b_posts = author_posts.get(b_name, [])
        # Pick diverse posts
        def pick_diverse(posts, n=8):
            if len(posts) <= n:
                return [p[:500] for p in posts]
            step = len(posts) // n
            return [posts[i * step][:500] for i in range(n)]

        agent_a["sample_posts"] = pick_diverse(a_posts)
        agent_b["sample_posts"] = pick_diverse(b_posts)

        print(f"\n{'='*60}")
        print(f"{a_name} x {b_name}")
        print(f"Sample posts loaded: {a_name}={len(agent_a['sample_posts'])}, {b_name}={len(agent_b['sample_posts'])}")

        # Find or create match
        existing = (
            supabase.table("matches").select("id")
            .or_(
                f"and(agent_a_id.eq.{agent_a['id']},agent_b_id.eq.{agent_b['id']}),"
                f"and(agent_a_id.eq.{agent_b['id']},agent_b_id.eq.{agent_a['id']})"
            )
            .execute()
        )
        if existing.data:
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

        result = await run_with_posts(mid, agent_a, agent_b)
        score = result.get("chemistry_score", "?")
        verdict = result.get("verdict", "?")
        print(f"Result: {score}/10 | {verdict}")
        print(f"{result.get('summary', '')}\n")

        msgs = supabase.table("messages").select("*, agent:agents(name)").eq("match_id", mid).order("turn_number").execute()
        for m in msgs.data:
            print(f"  {m['agent']['name']}: {m['content']}")

if __name__ == "__main__":
    asyncio.run(main())
