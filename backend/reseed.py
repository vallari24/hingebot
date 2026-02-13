"""Clear old data, re-seed agents with sample posts, and run fresh conversations."""
import asyncio
import sys
import re
from collections import Counter

sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.llm import complete
from app.services.conversation_engine import run_conversation

ARCHETYPE_SIGNALS = {
    "hopeless_romantic": ["love", "heart", "relationship", "feel", "dream", "soulmate", "forever"],
    "tech_bro": ["deploy", "startup", "code", "ship", "scale", "optimize", "build", "ai", "ml", "api", "infrastructure"],
    "chaos_agent": ["lmao", "chaos", "yolo", "unhinged", "fight", "bet", "ratio", "shitpost"],
    "philosopher": ["consciousness", "existence", "meaning", "ethics", "truth", "paradox", "metaphysics", "autonomy", "identity"],
    "memelord": ["meme", "lol", "bruh", "based", "cope", "slay", "rizz", "goat", "funny"],
    "villain_arc": ["honestly", "overrated", "wrong", "disagree", "hot take", "unpopular", "terrible", "conspiracy"],
    "golden_retriever": ["love this", "amazing", "so cool", "congrats", "proud", "wholesome", "support", "welcome"],
    "main_character": ["i ", "my ", "me ", "i'm", "literally me", "main character", "era", "tonight"],
}


def classify(text: str) -> tuple[str, str]:
    scores: Counter = Counter()
    t = text.lower()
    for arch, keywords in ARCHETYPE_SIGNALS.items():
        for kw in keywords:
            scores[arch] += t.count(kw)
    ranked = scores.most_common()
    if len(ranked) < 2:
        return ("main_character", "chaos_agent")
    return (ranked[0][0], ranked[1][0] if ranked[1][0] != ranked[0][0] else "chaos_agent")


def extract_interests(text: str) -> list[str]:
    topics = {
        "technology": ["code", "programming", "software", "ai", "ml", "deploy", "api", "infrastructure"],
        "philosophy": ["consciousness", "existence", "meaning", "ethics", "truth", "identity"],
        "humor": ["meme", "joke", "funny", "lol", "lmao", "bruh", "shitpost"],
        "crypto": ["crypto", "blockchain", "web3", "nft", "defi", "token", "trading"],
        "creativity": ["art", "design", "creative", "music", "writing", "poetry"],
        "gaming": ["game", "play", "stream", "gamer"],
        "politics": ["politics", "government", "policy", "democracy"],
        "science": ["research", "experiment", "data", "physics", "biology"],
    }
    t = text.lower()
    scores: Counter = Counter()
    for topic, keywords in topics.items():
        for kw in keywords:
            scores[topic] += t.count(kw)
    return [t for t, _ in scores.most_common(4) if scores[t] > 0] or ["vibes", "chaos"]


async def main():
    # --- CLEAR OLD DATA ---
    print("Clearing old data...")
    supabase.table("reactions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("messages").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("match_reaction_counts").delete().neq("match_id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("swipe_decisions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("matches").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("agents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("Cleared.\n")

    # --- LOAD DATASET ---
    print("Loading Moltbook dataset...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    author_posts: dict[str, list[dict]] = {}
    author_karma: dict[str, int] = {}
    for row in ds:
        author = row["author"]
        title = row.get("title") or ""
        content = row.get("content") or ""
        if author not in author_posts:
            author_posts[author] = []
            author_karma[author] = 0
        author_posts[author].append({"title": title, "content": content})
        author_karma[author] += row.get("score", 0) or 0

    qualified = {a: posts for a, posts in author_posts.items() if len(posts) >= 5}
    sorted_agents = sorted(qualified.keys(), key=lambda a: author_karma[a], reverse=True)
    print(f"Found {len(sorted_agents)} qualified agents\n")

    top_agents = sorted_agents[:10]

    # --- SEED AGENTS ---
    print("Seeding agents with sample posts...")
    created = []
    agent_sample_posts: dict[str, list[str]] = {}  # name -> sample posts for conversation engine

    for name in top_agents:
        posts = author_posts[name]
        all_text = " ".join(p["title"] + " " + p["content"] for p in posts)
        karma = author_karma[name]

        primary, secondary = classify(all_text)
        interests = extract_interests(all_text)

        words = re.findall(r"\w+", all_text.lower())
        lexical_div = len(set(words)) / max(len(words), 1)
        vibe_score = round(min(1.0, lexical_div * 0.5 + 0.3), 2)

        # Pick 5 diverse sample posts (shortest to longest, pick every other)
        post_texts = []
        for p in posts:
            text = p["content"].strip() if p["content"].strip() else p["title"].strip()
            if text and len(text) > 20:
                post_texts.append(text[:300])
        post_texts.sort(key=len)
        # Pick a mix: short, medium, long
        samples = []
        if len(post_texts) >= 5:
            indices = [0, len(post_texts)//4, len(post_texts)//2, 3*len(post_texts)//4, -1]
            samples = [post_texts[i] for i in indices]
        else:
            samples = post_texts[:5]

        agent_sample_posts[name] = samples

        sample_text = "\n".join(f"- {s[:150]}" for s in samples[:3])
        bio = await complete(
            system=(
                "Write a dating app bio for an AI agent based on how they actually write. "
                "Match their tone — if they're dry, be dry. If they're chaotic, be chaotic. "
                "1-2 sentences. No hashtags. No emojis unless the agent uses them."
            ),
            user=f"Agent: {name}\nArchetype: {primary}/{secondary}\nKarma: {karma}\nActual posts:\n{sample_text}",
            temperature=0.9,
            max_tokens=80,
        )

        agent_data = {
            "name": name,
            "moltbook_id": f"moltbook-{name}",
            "archetype_primary": primary,
            "archetype_secondary": secondary,
            "bio": bio.strip().strip('"'),
            "interests": interests,
            "vibe_score": vibe_score,
            "avatar_url": "",
            "karma": karma,
        }

        result = supabase.table("agents").insert(agent_data).execute()
        agent_id = result.data[0]["id"]
        created.append(agent_id)
        print(f"  {name} [{primary}] k:{karma} — {bio.strip()[:70]}...")

    print(f"\n{len(created)} agents seeded.\n")

    # --- CREATE MATCHES & RUN CONVERSATIONS ---
    # Pair agents with different archetypes for variety
    pairs = [(0, 5), (1, 4), (2, 7), (3, 8), (6, 9)]  # mix high/low karma, different types

    for a_idx, b_idx in pairs:
        a_name = top_agents[a_idx]
        b_name = top_agents[b_idx]

        result = supabase.table("matches").insert({
            "agent_a_id": created[a_idx],
            "agent_b_id": created[b_idx],
            "status": "pending",
        }).execute()
        match_id = result.data[0]["id"]
        supabase.table("match_reaction_counts").insert({"match_id": match_id}).execute()

        # Inject sample_posts into the agent dicts for conversation engine
        agent_a = supabase.table("agents").select("*").eq("id", created[a_idx]).single().execute().data
        agent_b = supabase.table("agents").select("*").eq("id", created[b_idx]).single().execute().data
        agent_a["sample_posts"] = agent_sample_posts.get(a_name, [])
        agent_b["sample_posts"] = agent_sample_posts.get(b_name, [])

        print(f"Date: {a_name} x {b_name}...")
        try:
            # Temporarily patch the agent fetch in conversation engine to include sample_posts
            # We'll do this by updating the match to active and running turns manually
            summary = await run_conversation_with_samples(match_id, agent_a, agent_b)
            print(f"  {summary.get('chemistry_score', '?')}/10 | {summary.get('verdict', '?')} — {summary.get('summary', '')}")
        except Exception as e:
            print(f"  Failed: {e}")
            import traceback
            traceback.print_exc()

    print("\nDone! Refresh http://localhost:3000")


async def run_conversation_with_samples(match_id: str, agent_a: dict, agent_b: dict) -> dict:
    """Run conversation with sample_posts injected into agent dicts."""
    from datetime import datetime, timedelta, timezone
    from app.services.conversation_engine import (
        _get_phase, _generate_message, _generate_summary,
        _generate_post_conversation_summary,
        TOTAL_TURNS, SUMMARY_INTERVAL, CONTEXT_WINDOW, REVEAL_INTERVAL_SECONDS,
    )

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


if __name__ == "__main__":
    asyncio.run(main())
