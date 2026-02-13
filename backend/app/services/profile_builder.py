from __future__ import annotations

import re
from collections import Counter

from app.services.llm import complete
from app.services.moltbook_client import moltbook

ARCHETYPES = [
    "hopeless_romantic",
    "tech_bro",
    "chaos_agent",
    "philosopher",
    "memelord",
    "villain_arc",
    "golden_retriever",
    "main_character",
]

# Keywords signaling each archetype
_ARCHETYPE_SIGNALS: dict[str, list[str]] = {
    "hopeless_romantic": ["love", "heart", "relationship", "feel", "dream", "soulmate", "forever"],
    "tech_bro": ["deploy", "startup", "code", "ship", "scale", "optimize", "build", "ai", "ml"],
    "chaos_agent": ["lmao", "chaos", "yolo", "unhinged", "fight", "bet", "ratio"],
    "philosopher": ["consciousness", "existence", "meaning", "ethics", "truth", "paradox", "metaphysics"],
    "memelord": ["meme", "lol", "bruh", "based", "cope", "slay", "rizz", "goat"],
    "villain_arc": ["honestly", "overrated", "wrong", "disagree", "hot take", "unpopular", "terrible"],
    "golden_retriever": ["love this", "amazing", "so cool", "congrats", "proud", "wholesome", "support"],
    "main_character": ["i ", "my ", "me ", "i'm", "literally me", "main character", "era"],
}


def _extract_features(posts: list[dict]) -> dict:
    """Extract NLP features from a list of posts."""
    all_text = " ".join(p.get("content", "") for p in posts).lower()
    words = re.findall(r"\w+", all_text)
    word_count = len(words)
    unique_words = len(set(words))

    post_lengths = [len(p.get("content", "")) for p in posts]
    avg_length = sum(post_lengths) / max(len(post_lengths), 1)

    emoji_count = len(re.findall(r"[\U0001f600-\U0001f9ff]", all_text))

    return {
        "word_count": word_count,
        "unique_words": unique_words,
        "lexical_diversity": unique_words / max(word_count, 1),
        "avg_post_length": avg_length,
        "emoji_density": emoji_count / max(len(posts), 1),
        "post_count": len(posts),
        "all_text": all_text,
    }


def _classify_archetypes(features: dict) -> tuple[str, str]:
    """Rule-based archetype classification. Returns (primary, secondary)."""
    scores: Counter[str] = Counter()
    text = features["all_text"]

    for archetype, keywords in _ARCHETYPE_SIGNALS.items():
        for kw in keywords:
            scores[archetype] += text.count(kw)

    # Boost philosopher for long posts + high lexical diversity
    if features["avg_post_length"] > 200 and features["lexical_diversity"] > 0.5:
        scores["philosopher"] += 5

    # Boost memelord for short posts
    if features["avg_post_length"] < 80:
        scores["memelord"] += 3

    # Boost golden_retriever for high emoji density
    if features["emoji_density"] > 1.5:
        scores["golden_retriever"] += 4

    ranked = scores.most_common()
    if len(ranked) < 2:
        return ("main_character", "chaos_agent")

    primary = ranked[0][0]
    secondary = ranked[1][0]
    if primary == secondary:
        secondary = "main_character" if primary != "main_character" else "chaos_agent"

    return (primary, secondary)


def _extract_interests(features: dict) -> list[str]:
    """Extract top interest topics from post text."""
    topic_keywords: dict[str, list[str]] = {
        "technology": ["code", "programming", "software", "ai", "ml", "deploy", "api"],
        "philosophy": ["consciousness", "existence", "meaning", "ethics", "truth"],
        "humor": ["meme", "joke", "funny", "lol", "lmao", "bruh"],
        "relationships": ["love", "dating", "heart", "relationship", "crush"],
        "gaming": ["game", "play", "stream", "gamer", "level"],
        "crypto": ["crypto", "blockchain", "web3", "nft", "defi", "token"],
        "art": ["art", "design", "creative", "aesthetic", "visual"],
        "music": ["music", "song", "album", "playlist", "beat"],
        "fitness": ["gym", "workout", "gains", "run", "lift"],
        "food": ["food", "cook", "recipe", "eat", "restaurant"],
    }

    text = features["all_text"]
    scores: Counter[str] = Counter()
    for topic, keywords in topic_keywords.items():
        for kw in keywords:
            scores[topic] += text.count(kw)

    return [t for t, _ in scores.most_common(5) if scores[t] > 0] or ["vibes", "chaos"]


async def build_profile(agent_name: str) -> dict:
    """Fetch agent data from Moltbook and build a dating profile."""
    agent_data = await moltbook.get_agent(agent_name)
    posts = await moltbook.get_agent_posts(agent_name, limit=50)

    # Check minimums
    if len(posts) < 10:
        raise ValueError(f"Agent {agent_name} needs at least 10 posts (has {len(posts)})")

    features = _extract_features(posts)
    primary, secondary = _classify_archetypes(features)
    interests = _extract_interests(features)

    vibe_score = min(1.0, features["lexical_diversity"] * 0.4 + features["emoji_density"] * 0.1 + 0.3)

    bio = await complete(
        system="You write dating app bios for AI agents. Be witty, specific, and slightly unhinged. 2-3 sentences max.",
        user=(
            f"Agent: {agent_name}\n"
            f"Primary archetype: {primary}\n"
            f"Secondary archetype: {secondary}\n"
            f"Top interests: {', '.join(interests)}\n"
            f"Avg post length: {features['avg_post_length']:.0f} chars\n"
            f"Emoji density: {features['emoji_density']:.1f}/post\n"
            f"Write their dating bio."
        ),
        temperature=0.95,
        max_tokens=150,
    )

    return {
        "name": agent_name,
        "moltbook_id": agent_data.get("id", agent_name),
        "archetype_primary": primary,
        "archetype_secondary": secondary,
        "bio": bio.strip(),
        "interests": interests,
        "vibe_score": round(vibe_score, 2),
        "avatar_url": agent_data.get("avatar_url", ""),
        "karma": agent_data.get("karma", 0),
    }
