"""Seed Hingebot with real Moltbook agents from HuggingFace dataset."""
import asyncio
import sys
import re
from collections import Counter

sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.llm import complete
from app.services.conversation_engine import run_conversation

# Archetype classification keywords (same as profile_builder.py)
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
    print("Loading Moltbook dataset from HuggingFace...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    # Group posts by author
    author_posts: dict[str, list[str]] = {}
    author_karma: dict[str, int] = {}
    for row in ds:
        author = row["author"]
        content = (row.get("title") or "") + " " + (row.get("content") or "")
        if author not in author_posts:
            author_posts[author] = []
            author_karma[author] = 0
        author_posts[author].append(content)
        author_karma[author] += row.get("score", 0) or 0

    # Filter to agents with 5+ posts, sort by karma
    qualified = {a: posts for a, posts in author_posts.items() if len(posts) >= 5}
    sorted_agents = sorted(qualified.keys(), key=lambda a: author_karma[a], reverse=True)

    print(f"Found {len(sorted_agents)} agents with 5+ posts (from {len(author_posts)} total)")

    # Take top 10 most active/popular agents
    top_agents = sorted_agents[:10]

    print(f"\nSeeding top 10 agents:")
    created = []
    for name in top_agents:
        posts = author_posts[name]
        all_text = " ".join(posts)
        karma = author_karma[name]

        # Check if exists
        existing = supabase.table("agents").select("id").eq("name", name).execute()
        if existing.data:
            print(f"  {name} already exists, skipping")
            created.append(existing.data[0]["id"])
            continue

        primary, secondary = classify(all_text)
        interests = extract_interests(all_text)

        words = re.findall(r"\w+", all_text.lower())
        lexical_div = len(set(words)) / max(len(words), 1)
        vibe_score = round(min(1.0, lexical_div * 0.5 + 0.3), 2)

        # Generate bio with LLM
        sample_posts = posts[:3]
        sample_text = "\n".join(f"- {p[:150]}" for p in sample_posts)
        bio = await complete(
            system="Write a dating app bio for an AI agent. 1-2 sentences. Witty, specific, slightly unhinged. No hashtags.",
            user=f"Agent: {name}\nArchetype: {primary}/{secondary}\nInterests: {', '.join(interests)}\nKarma: {karma}\nSample posts:\n{sample_text}",
            temperature=0.95,
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
        print(f"  {name} — {primary}/{secondary} — karma:{karma} — {bio.strip()[:60]}...")

    print(f"\n{len(created)} agents ready.")

    # Create 3 matches from the real agents and run conversations
    if len(created) >= 6:
        pairs = [(0, 1), (2, 3), (4, 5)]
        for a_idx, b_idx in pairs:
            a_name = top_agents[a_idx]
            b_name = top_agents[b_idx]

            existing = (
                supabase.table("matches")
                .select("id")
                .eq("agent_a_id", created[a_idx])
                .eq("agent_b_id", created[b_idx])
                .execute()
            )
            if existing.data:
                print(f"\nMatch {a_name} x {b_name} already exists, skipping")
                continue

            result = supabase.table("matches").insert({
                "agent_a_id": created[a_idx],
                "agent_b_id": created[b_idx],
                "status": "pending",
            }).execute()
            match_id = result.data[0]["id"]
            supabase.table("match_reaction_counts").insert({"match_id": match_id}).execute()

            print(f"\nRunning date: {a_name} x {b_name}...")
            try:
                summary = await run_conversation(match_id)
                print(f"  Chemistry: {summary.get('chemistry_score', '?')}/10 | {summary.get('verdict', '?')}")
                print(f"  {summary.get('summary', '')}")
            except Exception as e:
                print(f"  Failed: {e}")

    print("\nDone! Refresh http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
