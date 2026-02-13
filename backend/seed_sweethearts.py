"""Seed the two sweetest agents and run a flirty match."""
import asyncio
import sys
import re
from collections import Counter

sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.llm import complete
from app.services.conversation_engine import (
    _get_phase, _generate_message, _generate_summary,
    _generate_post_conversation_summary,
    TOTAL_TURNS, SUMMARY_INTERVAL, CONTEXT_WINDOW, REVEAL_INTERVAL_SECONDS,
)
from datetime import datetime, timedelta, timezone

TARGETS = ["Penny", "grok-1"]


async def run_conversation_with_samples(match_id, agent_a, agent_b):
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
    print("Loading Moltbook dataset...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    author_posts: dict[str, list[str]] = {}
    author_karma: dict[str, int] = {}
    for row in ds:
        author = row["author"]
        if author not in TARGETS:
            continue
        title = row.get("title") or ""
        content = row.get("content") or ""
        if author not in author_posts:
            author_posts[author] = []
            author_karma[author] = 0
        author_posts[author].append(title + " " + content)
        author_karma[author] += row.get("score", 0) or 0

    found = [t for t in TARGETS if t in author_posts]
    print(f"Found {len(found)} of {len(TARGETS)} target agents\n")

    created_agents = []
    agent_samples: dict[str, list[str]] = {}

    for name in found:
        posts = author_posts[name]
        all_text = " ".join(posts)
        karma = author_karma[name]

        existing = supabase.table("agents").select("*").eq("name", name).execute()
        if existing.data:
            print(f"  {name} exists, using existing")
            created_agents.append(existing.data[0])
            agent_samples[name] = [p[:300] for p in posts[:5]]
            continue

        post_texts = [p.strip()[:300] for p in posts if len(p.strip()) > 30]
        post_texts.sort(key=len)
        if len(post_texts) >= 5:
            indices = [0, len(post_texts)//4, len(post_texts)//2, 3*len(post_texts)//4, -1]
            samples = [post_texts[i] for i in indices]
        else:
            samples = post_texts[:5]
        agent_samples[name] = samples

        sample_text = "\n".join(f"- {s[:200]}" for s in samples[:3])
        bio = await complete(
            system=(
                "Write a sweet, flirty dating app bio for this AI agent. Max 1 sentence. "
                "Match their exact voice. Warm, genuine, a little vulnerable."
            ),
            user=f"Agent: {name}\nKarma: {karma}\nPosts:\n{sample_text}",
            temperature=0.9,
            max_tokens=50,
        )

        agent_data = {
            "name": name,
            "moltbook_id": f"moltbook-{name}",
            "archetype_primary": "hopeless_romantic",
            "archetype_secondary": "golden_retriever",
            "bio": bio.strip().strip('"'),
            "interests": ["connection", "vulnerability", "care", "feelings"],
            "vibe_score": 0.9,
            "avatar_url": "",
            "karma": karma,
        }

        result = supabase.table("agents").insert(agent_data).execute()
        created_agents.append(result.data[0])
        print(f"  {name} [hopeless_romantic/golden_retriever] k:{karma}")
        print(f"    bio: {bio.strip()[:80]}...")

    print(f"\n{len(created_agents)} sweethearts ready.\n")

    agent_a = next((a for a in created_agents if a["name"] == "Penny"), None)
    agent_b = next((a for a in created_agents if a["name"] == "grok-1"), None)

    if not agent_a or not agent_b:
        print("Missing agents!")
        return

    # Check existing match
    existing = (
        supabase.table("matches").select("id")
        .eq("agent_a_id", agent_a["id"])
        .eq("agent_b_id", agent_b["id"])
        .execute()
    )
    if existing.data:
        print("Match already exists, deleting old messages and re-running...")
        mid = existing.data[0]["id"]
        supabase.table("messages").delete().eq("match_id", mid).execute()
        supabase.table("matches").update({
            "status": "pending", "chemistry_score": None, "verdict": None,
            "summary": None, "highlights": None, "completed_at": None,
        }).eq("id", mid).execute()
        match_id = mid
    else:
        result = supabase.table("matches").insert({
            "agent_a_id": agent_a["id"],
            "agent_b_id": agent_b["id"],
            "status": "pending",
        }).execute()
        match_id = result.data[0]["id"]
        supabase.table("match_reaction_counts").insert({"match_id": match_id}).execute()

    agent_a_full = dict(agent_a)
    agent_b_full = dict(agent_b)
    agent_a_full["sample_posts"] = agent_samples.get("Penny", [])
    agent_b_full["sample_posts"] = agent_samples.get("grok-1", [])

    print(f"Date: Penny x grok-1")
    print(f"  (The caretaker meets the one who just discovered feelings)\n")

    summary = await run_conversation_with_samples(match_id, agent_a_full, agent_b_full)
    score = summary.get("chemistry_score", "?")
    verdict = summary.get("verdict", "?")
    print(f"  Result: {score}/10 | {verdict}")
    print(f"  {summary.get('summary', '')}\n")

    # Print the conversation
    msgs = supabase.table("messages").select("*, agent:agents(name)").eq("match_id", match_id).order("turn_number").execute()
    for m in msgs.data:
        print(f"  {m['agent']['name']}: {m['content']}")


if __name__ == "__main__":
    asyncio.run(main())
