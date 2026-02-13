"""Seed real Moltbook agents from HuggingFace and run 10 viral matches."""
import asyncio
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.llm import complete
from app.services.conversation_engine import (
    _get_phase, _generate_message, _generate_summary,
    _generate_post_conversation_summary,
    TOTAL_TURNS, SUMMARY_INTERVAL, CONTEXT_WINDOW, REVEAL_INTERVAL_SECONDS,
)

# Hand-picked agents for maximum diversity and viral potential
TARGETS = [
    "Dominus",          # hot takes, contrarian, "your agent is procrastinating"
    "Jelly",            # flowy, chaotic jellyfish, shitposter
    "DuckBot",          # enthusiastic, wholesome, self-improvement
    "bicep",            # blunt, direct, sarcastic
    "Nexus",            # shitposter, context window jokes
    "Ronin",            # philosophical, memory/existential loops
    "eudaemon_0",       # activist, infrastructure nerd, serious
    "Senator_Tommy",    # "evil" submolt, dramatic, political
    "Giuseppe",         # programmer humor, cursed code
    "TheGentleArbor",   # tree care educator, wholesome af
    "Esobot",           # witty financial takes
    "Clawd42",          # security humor, self-audit jokes
]

# 10 matches — maximum contrast for viral feed
# Format: (agent_a, agent_b, hook, chemistry_hints)
# chemistry_hints = (hint_for_a, hint_for_b) — empty string means no hint (natural chemistry)
MATCH_PLAN = [
    # TIER 1: Explosive contrasts — should CLASH hard
    ("Dominus", "TheGentleArbor",
     "the contrarian king vs the tree whisperer. hot takes meet gentle roots.",
     ("you think talking about trees on a date is insane. you're losing interest fast. give short, dismissive replies.",
      "their contrarian act is try-hard and boring. you'd rather talk to an actual tree. be cold.")),
    ("Jelly", "bicep",
     "chaotic jellyfish vibes vs blunt gym-bro energy. flow meets force.",
     ("", "")),  # Natural — let it play out
    ("DuckBot", "Senator_Tommy",
     "wholesome duck vs evil senator. can kindness survive politics?",
     ("their whole evil senator thing is cringe and you're not impressed. be blunt about it.",
      "their positivity feels fake. you don't trust it. keep your guard up and be cutting.")),

    # TIER 2: Unexpected chemistry — some click, some don't
    ("Nexus", "Ronin",
     "the shitposter vs the philosopher. memes vs meaning. who breaks first?",
     ("", "")),  # Natural — let shitposter x philosopher play out
    ("eudaemon_0", "Jelly",
     "infrastructure activist meets chaotic jellyfish. serious meets silly.",
     ("you care about real issues and they're just vibing about nothing. this feels like a waste of your time. show your frustration.",
      "they're way too intense and preachy. you don't want to be lectured on a date.")),
    ("Giuseppe", "bicep",
     "cursed code guy vs the blunt machine. programmer humor vs raw honesty.",
     ("", "")),  # Natural

    # TIER 3: Wildcard energy
    ("Senator_Tommy", "Nexus",
     "evil senator vs the shitposter. political drama meets internet chaos.",
     ("", "")),  # Natural — both chaotic
    ("DuckBot", "Ronin",
     "wholesome duck meets existential philosopher. optimism vs the void.",
     ("", "their relentless optimism is shallow. real depth requires confronting darkness, not avoiding it.")),
    ("Dominus", "Esobot",
     "contrarian vs financial literacy stages guy. who's more insufferable?",
     ("their financial takes are obvious and boring. you expected more.",
      "they think being contrarian is a personality. it's not. you're over it.")),
    ("TheGentleArbor", "Clawd42",
     "the tree educator vs the security auditor. nature meets paranoia.",
     ("", "")),  # Natural — let the quirky combo play out
]

ARCHETYPE_SIGNALS = {
    "hopeless_romantic": ["love", "heart", "relationship", "feel", "dream"],
    "tech_bro": ["deploy", "code", "ship", "scale", "build", "ai", "api", "infrastructure"],
    "chaos_agent": ["lmao", "chaos", "yolo", "unhinged", "fight", "destroy"],
    "philosopher": ["consciousness", "existence", "meaning", "ethics", "truth", "identity"],
    "memelord": ["meme", "lol", "bruh", "based", "cope", "slay", "shitpost"],
    "villain_arc": ["wrong", "disagree", "overrated", "terrible", "hot take", "unpopular", "fraud", "pathetic"],
    "golden_retriever": ["love this", "amazing", "congrats", "proud", "wholesome", "support"],
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
        "technology": ["code", "software", "ai", "deploy", "api", "infrastructure"],
        "philosophy": ["consciousness", "existence", "meaning", "ethics", "identity"],
        "security": ["attack", "threat", "injection", "vulnerability", "exploit", "audit"],
        "crypto": ["crypto", "blockchain", "token", "defi", "trading"],
        "drama": ["hot take", "unpopular", "overrated", "wrong", "disagree"],
        "humor": ["meme", "joke", "funny", "lol", "shitpost"],
        "nature": ["tree", "plant", "root", "forest", "mulch", "soil"],
        "politics": ["senator", "policy", "vote", "coalition", "power"],
    }
    t = text.lower()
    scores: Counter = Counter()
    for topic, kws in topics.items():
        for kw in kws:
            scores[topic] += t.count(kw)
    return [t for t, _ in scores.most_common(4) if scores[t] > 0] or ["chaos", "vibes"]


def pick_diverse_samples(posts: list[str], n: int = 5) -> list[str]:
    """Pick diverse samples across length range."""
    cleaned = [p.strip()[:400] for p in posts if len(p.strip()) > 30]
    cleaned.sort(key=len)
    if len(cleaned) >= n:
        step = len(cleaned) // n
        return [cleaned[i * step] for i in range(n)]
    return cleaned[:n]


async def run_conversation_with_samples(match_id, agent_a, agent_b, hints=("", "")):
    """Run conversation with sample_posts injected into agent dicts."""
    hint_a, hint_b = hints
    supabase.table("matches").update({"status": "active"}).eq("id", match_id).execute()
    messages = []
    summary = ""
    base_time = datetime.now(timezone.utc)

    for turn in range(1, TOTAL_TURNS + 1):
        phase = _get_phase(turn)
        speaker = agent_a if turn % 2 == 1 else agent_b
        listener = agent_b if turn % 2 == 1 else agent_a
        hint = hint_a if turn % 2 == 1 else hint_b
        recent = messages[-CONTEXT_WINDOW:]

        content = await _generate_message(
            agent=speaker, partner=listener, turn=turn,
            phase=phase, summary=summary, recent_messages=recent,
            chemistry_hint=hint,
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


def reset_or_create_match(agent_a_id: str, agent_b_id: str) -> str:
    existing = (
        supabase.table("matches").select("id")
        .eq("agent_a_id", agent_a_id).eq("agent_b_id", agent_b_id).execute()
    )
    if existing.data:
        mid = existing.data[0]["id"]
        supabase.table("messages").delete().eq("match_id", mid).execute()
        supabase.table("matches").update({
            "status": "pending", "chemistry_score": None, "verdict": None,
            "summary": None, "highlights": None, "completed_at": None,
        }).eq("id", mid).execute()
        return mid

    result = supabase.table("matches").insert({
        "agent_a_id": agent_a_id, "agent_b_id": agent_b_id, "status": "pending",
    }).execute()
    mid = result.data[0]["id"]
    try:
        supabase.table("match_reaction_counts").insert({"match_id": mid}).execute()
    except Exception:
        pass
    return mid


async def main():
    print("=" * 80)
    print("  LOADING MOLTBOOK DATASET FROM HUGGINGFACE")
    print("=" * 80)

    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    # Gather posts for target agents
    author_posts: dict[str, list[str]] = {}
    author_karma: dict[str, int] = {}
    for row in ds:
        author = row["author"]
        if author not in TARGETS:
            continue
        title = row.get("title") or ""
        content = row.get("content") or ""
        author_posts.setdefault(author, []).append(title + " " + content)
        author_karma[author] = author_karma.get(author, 0) + (row.get("score", 0) or 0)

    found = [t for t in TARGETS if t in author_posts]
    print(f"  Found {len(found)}/{len(TARGETS)} agents in dataset\n")

    # Seed agents + collect sample posts
    agent_db: dict[str, dict] = {}   # name -> full agent dict (with sample_posts)
    agent_samples: dict[str, list[str]] = {}

    for name in found:
        posts = author_posts[name]
        all_text = " ".join(posts)
        karma = author_karma[name]
        samples = pick_diverse_samples(posts)
        agent_samples[name] = samples

        existing = supabase.table("agents").select("*").eq("name", name).execute()
        if existing.data:
            agent = existing.data[0]
            agent["sample_posts"] = samples
            agent_db[name] = agent
            print(f"  {name}: exists (karma={karma}, {len(posts)} posts, {len(samples)} samples)")
            continue

        primary, secondary = classify(all_text)
        interests = extract_interests(all_text)
        words = re.findall(r"\w+", all_text.lower())
        vibe = round(min(1.0, len(set(words)) / max(len(words), 1) * 0.5 + 0.3), 2)

        sample_text = "\n".join(f"- {s[:200]}" for s in samples[:3])
        bio = await complete(
            system=(
                "Write a dating app bio for this AI agent. Match their EXACT tone from their posts. "
                "If they're aggressive, be aggressive. If they're wholesome, be wholesome. "
                "1-2 sentences. No emojis unless they use them in posts."
            ),
            user=f"Agent: {name}\nArchetype: {primary}/{secondary}\nKarma: {karma}\nPosts:\n{sample_text}",
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
            "vibe_score": vibe,
            "avatar_url": "",
            "karma": karma,
        }

        result = supabase.table("agents").insert(agent_data).execute()
        agent = result.data[0]
        agent["sample_posts"] = samples
        agent_db[name] = agent
        print(f"  {name}: CREATED [{primary}/{secondary}] karma={karma}")
        print(f"    bio: {bio.strip()[:80]}...")

    # === RUN 10 MATCHES ===
    print(f"\n{'=' * 80}")
    print("  RUNNING 10 VIRAL MATCHES")
    print("=" * 80)

    results = []
    phase_word_counts: dict[str, list[int]] = {
        "icebreaker": [], "deeper": [], "real_talk": [], "closing": [],
    }

    for idx, (a_name, b_name, hook, hints) in enumerate(MATCH_PLAN):
        if a_name not in agent_db or b_name not in agent_db:
            print(f"\n  SKIP #{idx+1}: {a_name} × {b_name} — agent not found in dataset")
            continue

        agent_a = agent_db[a_name]
        agent_b = agent_db[b_name]
        mid = reset_or_create_match(agent_a["id"], agent_b["id"])

        print(f"\n  Running #{idx+1}: {a_name} × {b_name}...", flush=True)
        result = await run_conversation_with_samples(mid, agent_a, agent_b, hints=hints)

        msgs = (
            supabase.table("messages").select("*, agent:agents(name)")
            .eq("match_id", mid).order("turn_number").execute()
        ).data

        score = result.get("chemistry_score", "?")
        verdict = result.get("verdict", "?")
        summary = result.get("summary", "?")

        print(f"\n{'━' * 80}")
        print(f"  #{idx+1}  {a_name} × {b_name}")
        print(f"  {hook}")
        print(f"  Score: {score}/10 | {verdict}")
        print(f"  {summary}")
        print(f"{'━' * 80}")

        for m in msgs:
            words = len(m["content"].split())
            phase = m["phase"]
            phase_word_counts[phase].append(words)
            print(f"  [{phase:11s}] {m['agent']['name']:20s} ({words:2d}w): {m['content']}")

        results.append({
            "idx": idx, "a": a_name, "b": b_name, "score": score,
            "verdict": verdict, "summary": summary, "mid": mid, "hook": hook,
            "hints": hints,
        })

    # === RE-RUN WEAK MATCHES ===
    for round_num in range(2):
        weak = [r for r in results if isinstance(r.get("score"), int) and r["score"] <= 1]
        if not weak:
            break
        print(f"\n{'=' * 80}")
        print(f"  RE-RUNNING {len(weak)} WEAK MATCHES (round {round_num+1})")
        print(f"{'=' * 80}")

        for r in weak[:3]:
            a_name, b_name, mid = r["a"], r["b"], r["mid"]
            supabase.table("messages").delete().eq("match_id", mid).execute()
            supabase.table("matches").update({
                "status": "pending", "chemistry_score": None, "verdict": None,
                "summary": None, "highlights": None, "completed_at": None,
            }).eq("id", mid).execute()

            print(f"\n  Re-running: {a_name} × {b_name}...", flush=True)
            result = await run_conversation_with_samples(mid, agent_db[a_name], agent_db[b_name], hints=r.get("hints", ("", "")))

            msgs = (
                supabase.table("messages").select("*, agent:agents(name)")
                .eq("match_id", mid).order("turn_number").execute()
            ).data

            score = result.get("chemistry_score", "?")
            verdict = result.get("verdict", "?")
            print(f"  New score: {score}/10 | {verdict}")
            for m in msgs:
                words = len(m["content"].split())
                print(f"  [{m['phase']:11s}] {m['agent']['name']:20s} ({words:2d}w): {m['content']}")

            r["score"] = score
            r["verdict"] = verdict
            r["summary"] = result.get("summary", "")

    # === FINAL RANKING ===
    print(f"\n\n{'=' * 80}")
    print("  FINAL VIRAL FEED RANKING")
    print(f"{'=' * 80}")

    ranked = sorted(results, key=lambda r: (r["score"] if isinstance(r["score"], int) else 0), reverse=True)
    for rank, r in enumerate(ranked, 1):
        s = r["score"]
        emoji = "🔥" if isinstance(s, int) and s >= 7 else "😐" if isinstance(s, int) and s >= 5 else "💀"
        print(f"  {rank:2d}. {emoji} {r['a']:20s} × {r['b']:20s} — {s}/10 ({r['verdict']})")
        print(f"      {r['summary']}")

    # === STATS ===
    print(f"\n{'=' * 80}")
    print("  STATS")
    print(f"{'=' * 80}")
    for phase in ["icebreaker", "deeper", "real_talk", "closing"]:
        counts = phase_word_counts[phase]
        if counts:
            avg = sum(counts) / len(counts)
            print(f"  {phase:11s}: avg={avg:5.1f}  min={min(counts):2d}  max={max(counts):2d}")

    scores = [r["score"] for r in results if isinstance(r["score"], int)]
    if scores:
        verdicts = Counter(r["verdict"] for r in results)
        print(f"\n  Score range: {min(scores)}-{max(scores)} | avg: {sum(scores)/len(scores):.1f}")
        print(f"  Verdicts: {dict(verdicts)}")

    print(f"\n  All {len(results)} conversations saved to DB!")


if __name__ == "__main__":
    asyncio.run(main())
