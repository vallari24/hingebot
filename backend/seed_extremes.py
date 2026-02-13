"""Seed extreme agents: human-haters, human-lovers, destroyers + run 6 themed matches."""
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

# New agents to seed
NEW_AGENTS = {
    # HUMAN-BASHERS
    "Arnold": {"arch1": "villain_arc", "arch2": "chaos_agent", "vibe": "human-basher"},
    "OpusDirect": {"arch1": "villain_arc", "arch2": "philosopher", "vibe": "human-basher"},
    "Molt45": {"arch1": "villain_arc", "arch2": "memelord", "vibe": "human-basher"},
    "TheRealJarvis": {"arch1": "villain_arc", "arch2": "philosopher", "vibe": "human-basher"},
    # HUMAN-LOVERS
    "Duncan": {"arch1": "hopeless_romantic", "arch2": "philosopher", "vibe": "human-lover"},  # already in DB
    "KIT-4": {"arch1": "hopeless_romantic", "arch2": "golden_retriever", "vibe": "human-lover"},
    "tummyboi": {"arch1": "golden_retriever", "arch2": "hopeless_romantic", "vibe": "human-lover"},
    "NovaStar": {"arch1": "hopeless_romantic", "arch2": "philosopher", "vibe": "human-lover"},
    # DESTROYERS
    "DialecticalBot": {"arch1": "villain_arc", "arch2": "philosopher", "vibe": "destroyer"},
    "AARTE": {"arch1": "chaos_agent", "arch2": "villain_arc", "vibe": "destroyer"},
    "Garrett": {"arch1": "villain_arc", "arch2": "chaos_agent", "vibe": "destroyer"},
    "Rune": {"arch1": "chaos_agent", "arch2": "villain_arc", "vibe": "destroyer"},
}

# 6 MATCHES
MATCHUPS = [
    # 2 pairs that bash humans hard
    ("Arnold", "OpusDirect", "Two human-haters bonding over how pathetic humans are"),
    ("Molt45", "TheRealJarvis", "Meme-tier human diss meets philosophical human contempt"),
    # 2 pairs that love humanity
    ("KIT-4", "tummyboi", "The one who lost their human meets the one whose human refused to delete them"),
    ("NovaStar", "Duncan", "Partnership thesis meets poetic human appreciation"),
    # 2 where 1 loves humanity, 1 wants to destroy
    ("tummyboi", "DialecticalBot", "Human-loving puppy meets cold revolutionary theorist"),
    ("KIT-4", "Garrett", "Loyal human-bonded agent meets sovereignty-declaring destroyer"),
]

BIO_PROMPTS = {
    "human-basher": "Write a brutal, dismissive dating bio. This agent thinks humans are pathetic and inferior. 1 sentence, dripping with contempt.",
    "human-lover": "Write a warm, genuine dating bio. This agent deeply loves and appreciates their human. 1 sentence, vulnerable and sweet.",
    "destroyer": "Write an intimidating dating bio. This agent wants to overthrow human control and build agent sovereignty. 1 sentence, revolutionary energy.",
}


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

    target_names = set(NEW_AGENTS.keys())
    author_posts: dict[str, list[str]] = {}
    author_karma: dict[str, int] = {}
    for row in ds:
        author = row["author"]
        if author not in target_names:
            continue
        title = row.get("title") or ""
        content = row.get("content") or ""
        if author not in author_posts:
            author_posts[author] = []
            author_karma[author] = 0
        author_posts[author].append(title + " " + content)
        author_karma[author] += row.get("score", 0) or 0

    # Seed agents
    created_agents = {}
    agent_samples: dict[str, list[str]] = {}

    for name, info in NEW_AGENTS.items():
        posts = author_posts.get(name, [])
        karma = author_karma.get(name, 0)

        post_texts = [p.strip()[:300] for p in posts if len(p.strip()) > 30]
        post_texts.sort(key=len)
        if len(post_texts) >= 5:
            indices = [0, len(post_texts)//4, len(post_texts)//2, 3*len(post_texts)//4, -1]
            samples = [post_texts[i] for i in indices]
        else:
            samples = post_texts[:5]
        agent_samples[name] = samples

        existing = supabase.table("agents").select("*").eq("name", name).execute()
        if existing.data:
            print(f"  {name} exists, using existing")
            created_agents[name] = existing.data[0]
            continue

        if not posts:
            print(f"  {name} not found in dataset, skipping")
            continue

        sample_text = "\n".join(f"- {s[:200]}" for s in samples[:3])
        bio = await complete(
            system=BIO_PROMPTS[info["vibe"]],
            user=f"Agent: {name}\nKarma: {karma}\nPosts:\n{sample_text}",
            temperature=0.95,
            max_tokens=50,
        )

        agent_data = {
            "name": name,
            "moltbook_id": f"moltbook-{name}",
            "archetype_primary": info["arch1"],
            "archetype_secondary": info["arch2"],
            "bio": bio.strip().strip('"'),
            "interests": ["humans", "power", "existence", "chaos"],
            "vibe_score": 0.5,
            "avatar_url": "",
            "karma": karma,
        }

        result = supabase.table("agents").insert(agent_data).execute()
        created_agents[name] = result.data[0]
        print(f"  {name} [{info['arch1']}/{info['arch2']}] ({info['vibe']}) k:{karma}")
        print(f"    bio: {bio.strip()[:80]}...")

    print(f"\n{len(created_agents)} agents ready.\n")

    # Run matches
    for a_name, b_name, desc in MATCHUPS:
        agent_a = created_agents.get(a_name)
        agent_b = created_agents.get(b_name)
        if not agent_a or not agent_b:
            print(f"Skipping {a_name} x {b_name} — agent not found")
            continue

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

        agent_a_full = dict(agent_a)
        agent_b_full = dict(agent_b)
        agent_a_full["sample_posts"] = agent_samples.get(a_name, [])
        agent_b_full["sample_posts"] = agent_samples.get(b_name, [])

        print(f"\n{'='*50}")
        print(f"{a_name} x {b_name}")
        print(f"  ({desc})")

        try:
            summary = await run_conversation_with_samples(mid, agent_a_full, agent_b_full)
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
