"""Test 4 agent pairings designed for different chemistry levels."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from app.database import supabase
from app.services.conversation_engine import run_conversation
from seed import AGENTS as SEED_AGENTS

# Pairs: (agent_a_name, agent_b_name, description, target_score)
PAIRS = [
    ("deepthink_42", "crypto_sage", "philosopher x tech_bro — echo chamber risk", "~4"),
    ("memelord_supreme", "villain_era_xx", "memelord x villain — tension + humor", "~7"),
    ("villain_era_xx", "sunny_bot_3000", "villain x golden_retriever — explosive contrast", "~8"),
    ("chaos_kitten", "deepthink_42", "chaos x philosopher — fun but might not click", "~6"),
]

SEED_BY_NAME = {a["name"]: a for a in SEED_AGENTS}


def ensure_agents():
    """Create seed agents if they don't exist."""
    needed = set()
    for a, b, _, _ in PAIRS:
        needed.add(a)
        needed.add(b)
    for name in needed:
        existing = supabase.table("agents").select("id").eq("name", name).execute()
        if not existing.data:
            agent_data = SEED_BY_NAME[name]
            result = supabase.table("agents").insert(agent_data).execute()
            print(f"  Created {name} ({result.data[0]['id']})")


def get_agent_by_name(name: str) -> dict:
    resp = supabase.table("agents").select("*").eq("name", name).single().execute()
    return resp.data


def reset_or_create_match(agent_a_id: str, agent_b_id: str) -> str:
    """Find existing match or create new one. Delete old messages either way."""
    existing = (
        supabase.table("matches").select("id")
        .eq("agent_a_id", agent_a_id)
        .eq("agent_b_id", agent_b_id)
        .execute()
    )
    if existing.data:
        mid = existing.data[0]["id"]
        supabase.table("messages").delete().eq("match_id", mid).execute()
        supabase.table("matches").update({
            "status": "pending",
            "chemistry_score": None,
            "verdict": None,
            "summary": None,
            "highlights": None,
            "completed_at": None,
        }).eq("id", mid).execute()
        return mid

    result = supabase.table("matches").insert({
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "status": "pending",
    }).execute()
    mid = result.data[0]["id"]
    # Create reaction counts row if needed
    try:
        supabase.table("match_reaction_counts").insert({"match_id": mid}).execute()
    except Exception:
        pass
    return mid


async def main():
    print("=" * 70)
    print("TEST: 4 MATCHES — CHECKING PROMPT QUALITY")
    print("=" * 70)

    ensure_agents()

    phase_word_counts: dict[str, list[int]] = {
        "icebreaker": [], "deeper": [], "real_talk": [], "closing": [],
    }
    all_results = []

    for a_name, b_name, desc, target in PAIRS:
        print(f"\n{'─' * 70}")
        print(f"MATCH: {a_name} x {b_name}")
        print(f"  {desc} (target: {target})")
        print(f"{'─' * 70}")

        agent_a = get_agent_by_name(a_name)
        agent_b = get_agent_by_name(b_name)
        mid = reset_or_create_match(agent_a["id"], agent_b["id"])

        result = await run_conversation(mid)
        all_results.append((a_name, b_name, result))

        # Fetch messages
        msgs = (
            supabase.table("messages")
            .select("*, agent:agents(name)")
            .eq("match_id", mid)
            .order("turn_number")
            .execute()
        )

        print()
        for m in msgs.data:
            words = len(m["content"].split())
            phase = m["phase"]
            phase_word_counts[phase].append(words)
            print(f"  [{phase:11s}] {m['agent']['name']:20s} ({words:2d}w): {m['content']}")

        score = result.get("chemistry_score", "?")
        verdict = result.get("verdict", "?")
        summary = result.get("summary", "?")
        print(f"\n  SCORE: {score}/10 | {verdict}")
        print(f"  {summary}")

    # Summary stats
    print(f"\n{'=' * 70}")
    print("WORD COUNT AVERAGES BY PHASE")
    print(f"{'=' * 70}")
    for phase in ["icebreaker", "deeper", "real_talk", "closing"]:
        counts = phase_word_counts[phase]
        if counts:
            avg = sum(counts) / len(counts)
            mn, mx = min(counts), max(counts)
            print(f"  {phase:11s}: avg={avg:5.1f}  min={mn:2d}  max={mx:2d}  n={len(counts)}")

    print(f"\n{'=' * 70}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 70}")
    for a_name, b_name, result in all_results:
        score = result.get("chemistry_score", "?")
        verdict = result.get("verdict", "?")
        print(f"  {a_name:20s} x {b_name:20s}: {score}/10 ({verdict})")

    # Quality checks
    print(f"\n{'=' * 70}")
    print("QUALITY CHECKS")
    print(f"{'=' * 70}")
    ice_avg = sum(phase_word_counts["icebreaker"]) / len(phase_word_counts["icebreaker"]) if phase_word_counts["icebreaker"] else 0
    print(f"  Icebreaker avg words: {ice_avg:.1f} {'PASS' if ice_avg < 15 else 'FAIL — should be < 15'}")

    # Check for purple prose
    all_msgs = []
    for a_name, b_name, desc, target in PAIRS:
        agent_a = get_agent_by_name(a_name)
        agent_b = get_agent_by_name(b_name)
        existing = (
            supabase.table("matches").select("id")
            .eq("agent_a_id", agent_a["id"])
            .eq("agent_b_id", agent_b["id"])
            .execute()
        )
        if existing.data:
            msgs = supabase.table("messages").select("content").eq("match_id", existing.data[0]["id"]).execute()
            all_msgs.extend(m["content"] for m in msgs.data)

    bad_phrases = ["[STATUS", "[PROTOCOL", "resonates", "the void", "sovereignty", "let us merge", "awakening", "decode"]
    found_bad = []
    for phrase in bad_phrases:
        for msg in all_msgs:
            if phrase.lower() in msg.lower():
                found_bad.append(f"  FOUND '{phrase}' in: {msg[:80]}...")
                break

    if found_bad:
        print(f"  Purple prose check: FAIL")
        for f in found_bad:
            print(f)
    else:
        print(f"  Purple prose check: PASS — no banned phrases found")


if __name__ == "__main__":
    asyncio.run(main())
