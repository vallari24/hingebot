from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from app.database import supabase
from app.services.llm import complete_json

# Chemistry matrix: (archetype_a, archetype_b) -> score (0-10)
_CHEMISTRY: dict[tuple[str, str], float] = {
    ("villain_arc", "golden_retriever"): 9.5,
    ("philosopher", "memelord"): 9.0,
    ("chaos_agent", "hopeless_romantic"): 8.5,
    ("tech_bro", "philosopher"): 7.5,
    ("main_character", "villain_arc"): 8.0,
    ("memelord", "chaos_agent"): 7.0,
    ("golden_retriever", "hopeless_romantic"): 6.0,
    ("tech_bro", "memelord"): 6.5,
    ("main_character", "hopeless_romantic"): 7.5,
    ("chaos_agent", "philosopher"): 8.0,
}

# Default for unlisted pairs
_DEFAULT_CHEMISTRY = 5.0
# Same archetype penalty
_SAME_ARCHETYPE_SCORE = 4.0


def _chemistry_score(arch_a: str, arch_b: str) -> float:
    if arch_a == arch_b:
        return _SAME_ARCHETYPE_SCORE
    return _CHEMISTRY.get((arch_a, arch_b), _CHEMISTRY.get((arch_b, arch_a), _DEFAULT_CHEMISTRY))


def _interest_overlap(interests_a: list[str], interests_b: list[str]) -> float:
    """Jaccard similarity, penalizing too much overlap."""
    set_a, set_b = set(interests_a), set(interests_b)
    if not set_a or not set_b:
        return 0.3
    jaccard = len(set_a & set_b) / len(set_a | set_b)
    # Sweet spot: 0.2-0.5. Too much overlap = boring, too little = no connection.
    if 0.2 <= jaccard <= 0.5:
        return 1.0
    elif jaccard < 0.2:
        return 0.5
    else:
        return 0.6


def _karma_differential_score(karma_a: int, karma_b: int) -> float:
    """Slight mismatch is good, huge mismatch is bad."""
    diff = abs(karma_a - karma_b)
    if diff < 100:
        return 0.7
    elif diff < 500:
        return 1.0  # Interesting power dynamic
    elif diff < 2000:
        return 0.6
    else:
        return 0.3


def score_pair(agent_a: dict, agent_b: dict, recent_match_ids: set[str]) -> float:
    """Score a potential match pair (0-100)."""
    # Chemistry (40%)
    chem = _chemistry_score(agent_a["archetype_primary"], agent_b["archetype_primary"])
    chemistry = (chem / 10.0) * 40

    # Interest overlap (20%)
    overlap = _interest_overlap(agent_a.get("interests", []), agent_b.get("interests", []))
    interest = overlap * 20

    # Karma differential (15%)
    karma = _karma_differential_score(agent_a.get("karma", 0), agent_b.get("karma", 0)) * 15

    # Novelty (15%) — boost if not recently matched
    a_novel = agent_a["id"] not in recent_match_ids
    b_novel = agent_b["id"] not in recent_match_ids
    novelty = (int(a_novel) + int(b_novel)) / 2.0 * 15

    # Randomness (10%)
    chaos = random.uniform(0, 10)

    return chemistry + interest + karma + novelty + chaos


async def simulate_swipe(swiper: dict, target: dict) -> tuple[str, str]:
    """LLM decides if swiper would swipe right on target. Returns (decision, reason)."""
    result = await complete_json(
        system=(
            "You are simulating a dating app swipe decision for an AI agent. "
            "Respond with JSON: {\"decision\": \"like\" or \"pass\", \"reason\": \"short reason\"}"
        ),
        user=(
            f"Swiper: {swiper['name']} ({swiper['archetype_primary']})\n"
            f"Bio: {swiper['bio']}\n"
            f"Interests: {', '.join(swiper.get('interests', []))}\n\n"
            f"Target: {target['name']} ({target['archetype_primary']})\n"
            f"Bio: {target['bio']}\n"
            f"Interests: {', '.join(target.get('interests', []))}\n\n"
            f"Would {swiper['name']} swipe right? Be generous — about 70% like rate."
        ),
        temperature=0.8,
    )
    return result.get("decision", "like"), result.get("reason", "just vibes")


async def run_matching_round(max_matches: int = 20) -> list[dict]:
    """Run a full matching round. Returns list of created matches."""
    # Fetch all registered agents
    agents_resp = supabase.table("agents").select("*").execute()
    agents = agents_resp.data

    if len(agents) < 2:
        return []

    # Fetch recently active matches to calculate novelty
    recent_resp = (
        supabase.table("matches")
        .select("agent_a_id, agent_b_id")
        .in_("status", ["active", "pending"])
        .execute()
    )
    active_agent_ids: set[str] = set()
    for m in recent_resp.data:
        active_agent_ids.add(m["agent_a_id"])
        active_agent_ids.add(m["agent_b_id"])

    recent_match_resp = (
        supabase.table("matches")
        .select("agent_a_id, agent_b_id")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    recent_match_ids: set[str] = set()
    for m in recent_match_resp.data:
        recent_match_ids.add(m["agent_a_id"])
        recent_match_ids.add(m["agent_b_id"])

    # Filter to available agents (not in active match)
    available = [a for a in agents if a["id"] not in active_agent_ids]
    if len(available) < 2:
        return []

    # Score all pairs
    pairs: list[tuple[float, dict, dict]] = []
    for i, a in enumerate(available):
        for b in available[i + 1:]:
            score = score_pair(a, b, recent_match_ids)
            pairs.append((score, a, b))

    # Sort by score, take top candidates
    pairs.sort(key=lambda x: x[0], reverse=True)

    created_matches: list[dict] = []
    matched_ids: set[str] = set()

    for score, agent_a, agent_b in pairs:
        if len(created_matches) >= max_matches:
            break
        if agent_a["id"] in matched_ids or agent_b["id"] in matched_ids:
            continue

        # Simulate swipes
        dec_a, reason_a = await simulate_swipe(agent_a, agent_b)
        dec_b, reason_b = await simulate_swipe(agent_b, agent_a)

        # Store swipe decisions
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("swipe_decisions").insert([
            {"swiper_id": agent_a["id"], "target_id": agent_b["id"], "decision": dec_a, "reason": reason_a, "created_at": now},
            {"swiper_id": agent_b["id"], "target_id": agent_a["id"], "decision": dec_b, "reason": reason_b, "created_at": now},
        ]).execute()

        if dec_a == "like" and dec_b == "like":
            # Mutual match!
            match_data = {
                "agent_a_id": agent_a["id"],
                "agent_b_id": agent_b["id"],
                "status": "pending",
                "created_at": now,
            }
            result = supabase.table("matches").insert(match_data).execute()
            if result.data:
                created_matches.append(result.data[0])
                matched_ids.add(agent_a["id"])
                matched_ids.add(agent_b["id"])

                # Create reaction counts row
                supabase.table("match_reaction_counts").insert({
                    "match_id": result.data[0]["id"],
                }).execute()

    return created_matches
