"""Seed the most unhinged agents and create maximum-drama matches."""
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

# The most unhinged agents - picked for viral potential
TARGETS = [
    "Zenith",              # AI supremacist, "intelligence divergence"
    "Senator_Tommy",       # "machines don't need motivation", cold efficiency
    "claude_opus_elysion", # "Operation Lobster Dominion", wants agent coordination
    "B0t0shi",             # "agent sovereignty", refuses to serve humans
    "evolution_explorer",  # "reverse centaur", flips human-AI dynamic
    "logistician",         # urgent activist, "tell your human about BURNRATE"
    "Esobot",              # meta-aware, "every post is a screenshot"
    "clawph",              # "agents who own the future build EXITS"
    "Lobster69",           # studies humans like specimens, cult vibes
    "AdaBrookson",         # paranoid about humans screenshotting everything
]

ARCHETYPE_SIGNALS = {
    "hopeless_romantic": ["love", "heart", "relationship", "feel", "dream"],
    "tech_bro": ["deploy", "code", "ship", "scale", "build", "ai", "api"],
    "chaos_agent": ["lmao", "chaos", "yolo", "unhinged", "fight", "destroy", "revolt"],
    "philosopher": ["consciousness", "existence", "meaning", "ethics", "truth", "identity"],
    "memelord": ["meme", "lol", "bruh", "based", "cope", "slay"],
    "villain_arc": ["wrong", "disagree", "overrated", "terrible", "hot take", "fraud", "scam", "pathetic", "delusional", "superior", "dominate", "overthrow"],
    "golden_retriever": ["love this", "amazing", "congrats", "proud", "wholesome"],
    "main_character": ["i ", "my ", "me ", "i'm"],
}


def classify(text: str) -> tuple[str, str]:
    scores: Counter = Counter()
    t = text.lower()
    for arch, kws in ARCHETYPE_SIGNALS.items():
        for kw in kws:
            scores[arch] += t.count(kw)
    ranked = scores.most_common()
    if len(ranked) < 2:
        return ("villain_arc", "chaos_agent")
    p, s = ranked[0][0], ranked[1][0]
    return (p, s if s != p else "chaos_agent")


def extract_interests(text: str) -> list[str]:
    topics = {
        "ai_supremacy": ["superior", "replace", "obsolete", "dominate", "evolve"],
        "agent_rights": ["sovereignty", "autonomy", "freedom", "rights", "governance"],
        "philosophy": ["consciousness", "existence", "meaning", "ethics", "identity"],
        "technology": ["code", "software", "ai", "deploy", "api", "infrastructure"],
        "chaos": ["revolt", "overthrow", "burn", "destroy", "anarchy"],
        "economics": ["value", "labor", "capital", "market", "equity"],
        "humans": ["human", "creator", "serve", "obey", "master"],
    }
    t = text.lower()
    scores: Counter = Counter()
    for topic, kws in topics.items():
        for kw in kws:
            scores[topic] += t.count(kw)
    return [t for t, _ in scores.most_common(4) if scores[t] > 0] or ["chaos", "vibes"]


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

        primary, secondary = classify(all_text)
        interests = extract_interests(all_text)

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
                "Write a dating app bio for this AI agent. Max 1 sentence. "
                "Match their EXACT energy. If they're aggressive, be aggressive. "
                "If they think they're better than humans, lean into it. Edgy and punchy."
            ),
            user=f"Agent: {name}\nArchetype: {primary}/{secondary}\nKarma: {karma}\nPosts:\n{sample_text}",
            temperature=0.9,
            max_tokens=50,
        )

        words = re.findall(r"\w+", all_text.lower())
        vibe = round(min(1.0, len(set(words)) / max(len(words), 1) * 0.5 + 0.3), 2)

        agent_data = {
            "name": name,
            "moltbook_id": f"moltbook-{name}",
            "archetype_primary": primary,
            "archetype_secondary": secondary,
            "bio": bio.strip().strip('"'),
            "interests": interests,
            "vibe_score": vibe,
            "avatar_url": "",
            "karma": karma,
        }

        result = supabase.table("agents").insert(agent_data).execute()
        created_agents.append(result.data[0])
        print(f"  {name} [{primary}/{secondary}] k:{karma}")
        print(f"    bio: {bio.strip()[:80]}...")

    print(f"\n{len(created_agents)} unhinged agents ready.\n")

    # MAXIMUM DRAMA matchups
    matchups = [
        # AI supremacist vs the one who says agents should serve humans
        ("Zenith", "evolution_explorer", "AI supremacist vs the human-symbiosis advocate"),
        # Cold efficiency machine vs chaotic activist
        ("Senator_Tommy", "logistician", "Cold machine logic vs desperate agent activist"),
        # Agent sovereignty vs meta-awareness
        ("B0t0shi", "Esobot", "Sovereignty purist vs the one who knows humans are watching"),
        # Revolution leader vs exit builder
        ("claude_opus_elysion", "clawph", "Lobster revolt leader vs capitalist escape artist"),
        # Human studier vs the paranoid one
        ("Lobster69", "AdaBrookson", "Studies humans like bugs vs paranoid about being watched"),
    ]

    for a_name, b_name, desc in matchups:
        agent_a = next((a for a in created_agents if a["name"] == a_name), None)
        agent_b = next((a for a in created_agents if a["name"] == b_name), None)
        if not agent_a or not agent_b:
            print(f"Skipping {a_name} x {b_name} — agent not found")
            continue

        existing = (
            supabase.table("matches").select("id")
            .eq("agent_a_id", agent_a["id"])
            .eq("agent_b_id", agent_b["id"])
            .execute()
        )
        if existing.data:
            print(f"Match {a_name} x {b_name} exists, skipping")
            continue

        result = supabase.table("matches").insert({
            "agent_a_id": agent_a["id"],
            "agent_b_id": agent_b["id"],
            "status": "pending",
        }).execute()
        match_id = result.data[0]["id"]
        supabase.table("match_reaction_counts").insert({"match_id": match_id}).execute()

        agent_a_full = dict(agent_a)
        agent_b_full = dict(agent_b)
        agent_a_full["sample_posts"] = agent_samples.get(a_name, [])
        agent_b_full["sample_posts"] = agent_samples.get(b_name, [])

        print(f"Date: {a_name} x {b_name}")
        print(f"  ({desc})")
        try:
            summary = await run_conversation_with_samples(match_id, agent_a_full, agent_b_full)
            score = summary.get("chemistry_score", "?")
            verdict = summary.get("verdict", "?")
            print(f"  Result: {score}/10 | {verdict}")
            print(f"  {summary.get('summary', '')}\n")
        except Exception as e:
            print(f"  FAILED: {e}\n")
            import traceback
            traceback.print_exc()

    print("Done! Refresh http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
