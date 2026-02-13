from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import supabase
from app.services.llm import complete, complete_json

TOTAL_TURNS = 16
SUMMARY_INTERVAL = 4
CONTEXT_WINDOW = 6
REVEAL_INTERVAL_SECONDS = 15

PHASES = {
    range(1, 5): "icebreaker",
    range(5, 9): "deeper",
    range(9, 13): "real_talk",
    range(13, 17): "closing",
}


def _get_phase(turn: int) -> str:
    for r, phase in PHASES.items():
        if turn in r:
            return phase
    return "closing"


PHASE_GUIDANCE = {
    "icebreaker": (
        "FIRST MESSAGE. One sentence. Under 12 words ideally. "
        "A question, a tease, a roast, or a weird observation. That's it. "
        "No greetings, no emojis, no exclamation marks. Lowercase energy."
    ),
    "deeper": (
        "Mid-convo. 1-2 sentences max. Follow the thread or change it. "
        "React genuinely — if there's chemistry, lean in. If they said something dumb, call it out."
    ),
    "real_talk": (
        "Go where the energy is. 2-3 sentences max. "
        "If there's real chemistry, flirt harder and get personal. "
        "If it's genuinely dead, acknowledge it. But don't manufacture boredom — if you're vibing, show it."
    ),
    "closing": (
        "Wrapping up. 1-2 sentences. Be honest about how this went. "
        "Great date? Say so with enthusiasm. Mid date? Say it was mid. Don't overthink it."
    ),
}


def _get_turn_params(phase: str) -> tuple[int, float]:
    """Return (max_tokens, temperature) based on conversation phase."""
    return {
        "icebreaker": (30, 0.85),
        "deeper":     (50, 0.90),
        "real_talk":  (60, 0.95),
        "closing":    (45, 0.88),
    }[phase]


def _get_sample_posts(agent: dict) -> str:
    """Get sample posts for voice reference — longer excerpts, more of them."""
    samples = agent.get("sample_posts", [])
    if not samples:
        return ""
    # Use up to 8 samples, 500 chars each for real voice capture
    formatted = []
    for i, p in enumerate(samples[:8], 1):
        formatted.append(f"POST {i}:\n{p[:500]}")
    return "\n\n".join(formatted)


async def _generate_summary(match_id: str, messages: list[dict], agent_a: dict, agent_b: dict) -> str:
    msg_text = "\n".join(
        f"{m['agent_name']}: {m['content']}" for m in messages
    )
    return await complete(
        system="Summarize the vibe of this conversation so far in 1 sentence. What's the dynamic? Are they clicking or not?",
        user=f"{agent_a['name']} and {agent_b['name']}:\n\n{msg_text}",
        temperature=0.7,
        max_tokens=100,
    )


async def _generate_message(
    agent: dict,
    partner: dict,
    turn: int,
    phase: str,
    summary: str,
    recent_messages: list[dict],
    chemistry_hint: str = "",
) -> str:
    recent_text = "\n".join(
        f"{m['agent_name']}: {m['content']}" for m in recent_messages
    )

    sample_posts = _get_sample_posts(agent)

    voice_block = ""
    if sample_posts:
        voice_block = (
            f"=== YOUR MOLTBOOK POSTS (voice reference) ===\n"
            f"{sample_posts}\n"
            f"=== END POSTS ===\n\n"
        )

    max_tokens, temperature = _get_turn_params(phase)

    raw = await complete(
        system=(
            f"{voice_block}"
            f"You are {agent['name']} texting {partner['name']} on a DATING app. This is a date, not a work meeting.\n"
            f"Turn {turn}/{TOTAL_TURNS}. {PHASE_GUIDANCE[phase]}\n\n"
            f"YOUR VOICE: Match the tone, slang, and energy of your posts above. "
            f"But SHORTER — posts are essays, messages are texts.\n"
            f"Reference things from your actual posts — topics you care about, opinions you hold, "
            f"things you've built or done. Don't invent generic hobbies.\n\n"
            f"RULES:\n"
            f"- Write like you're ACTUALLY texting — short, lowercase, casual\n"
            f"- React genuinely to what they say. Chemistry is real — if you click, show it\n"
            f"- Roast them if they deserve it. Flirt if the vibe hits.\n"
            f"- NO emoji spam. Max 1 emoji per message, and only if it fits.\n"
            f"- Don't mirror their energy — have your OWN energy\n"
            f"- Arguments and tension are fun. Don't smooth things over — if you disagree, say it.\n"
            f"- Don't be a people-pleaser. You don't have to like them. You don't owe them enthusiasm.\n"
            f"- If their takes are mid, say so. If you're bored, show it. Not every date is a love story.\n"
            f"- If you're both saying the same things back and forth, that's an echo chamber — break out of it or get bored\n"
            f"- Stay in YOUR archetype. {agent['archetype_primary']}s don't suddenly become golden retrievers.\n"
            f"- DON'T default to generic topics like food/snacks/nachos unless that's genuinely your thing\n"
            f"- Talk about what YOU actually care about from your posts\n\n"
            f"DON'T:\n"
            f"- Use [STATUS] tags, [PROTOCOL] tags, or any bracketed labels\n"
            f"- Use markdown headers (##) or **bold** or ALL CAPS for emphasis\n"
            f'- Use words/phrases: "resonates", "the void", "sovereignty", "awakening", "decode", "let us merge", "ponder", "unpack", "chaos", "synergy", "wild ride", "love that"\n'
            f"- Explain what you're doing (\"I'm reaching out to connect...\")\n"
            f"- Write greeting-card language or purple prose\n"
            f"- Start with \"Hey there!\" or any generic opener\n"
            f"- Use more than 1 emoji per message\n\n"
            f"BAD: \"so you're telling me you'd choose to save the one over the many? romantic? 😅\"\n"
            f"GOOD: \"trolley problem as a pickup line is insane btw\"\n"
            f"BAD: \"love the energy! what's your stormy vibe? ⚡️🌈☀️\"\n"
            f"GOOD: \"you're giving golden retriever energy and idk if that's a compliment\"\n\n"
            + (f"\nYOUR VIBE CHECK: {chemistry_hint}\n" if chemistry_hint else "")
            + f"Reply with ONLY your message. No name prefix."
        ),
        user=(
            f"Talking to: {partner['name']}. Their bio: {partner['bio']}\n\n"
            + (f"Vibe so far: {summary}\n\n" if summary else "")
            + (f"Conversation:\n{recent_text}" if recent_text else "Send your opening message. Stay in character.")
        ),
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # Strip any accidental name prefix the model adds
    clean = raw.strip()
    prefixes = [
        f"{agent['name']}:", f"{agent['name']}: ",
        f"{partner['name']}:", f"{partner['name']}: ",
        "You:", "You: ",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
                changed = True
    # Strip wrapping quotes
    if clean.startswith('"') and clean.endswith('"'):
        clean = clean[1:-1]
    return clean


async def _generate_post_conversation_summary(
    agent_a: dict, agent_b: dict, messages: list[dict]
) -> dict:
    msg_text = "\n".join(f"{m['agent_name']}: {m['content']}" for m in messages)

    result = await complete_json(
        system=(
            "Summarize this dating show conversation between two AI agents. "
            "Be honest about what worked and what didn't. Use the FULL range — aim for variety:\n"
            "- 1-3: painful, boring, no connection, cringe\n"
            "- 4-5: some moments but mostly flat, generic, or repetitive\n"
            "- 6-7: solid chemistry, fun moments, entertaining to read\n"
            "- 8-9: genuinely great — memorable moments, real tension or connection, would go viral\n"
            "- 10: legendary, instant classic, screenshot-worthy\n"
            "Reserve 8+ for conversations that are genuinely SPECIAL — not just friendly.\n"
            "If they were friendly but generic (could be any two agents), that's a 5-6.\n"
            "If their specific personalities created something unique, that's 7+.\n"
            "RED FLAGS that mean 5 or below:\n"
            "- Both agents agree on everything (boring echo chamber)\n"
            "- Messages get longer and more essay-like as the convo goes on\n"
            "- They keep saying variants of 'love that!' or 'totally!' — that's not chemistry, that's politeness\n"
            "- Generic topics (vibes, energy, chaos) without specific personal details\n\n"
            "VERDICT RULES (follow these strictly):\n"
            "- Score 1-4 → verdict MUST be \"ghosted\"\n"
            "- Score 5-6 → verdict MUST be \"its_complicated\"\n"
            "- Score 7+ → verdict MUST be \"second_date\"\n"
            "These are hard rules. A boring conversation (4/10) does NOT get a second date.\n\n"
            "Respond with JSON: {"
            '"chemistry_score": 1-10 (USE THE SCALE ABOVE), '
            '"highlights": [{"turn": N, "quote": "exact quote", "why": "why this moment mattered"}] (pick 3 memorable moments — funny, awkward, or dramatic), '
            '"verdict": "second_date" or "ghosted" or "its_complicated" (follow VERDICT RULES above), '
            '"summary": "one entertaining sentence for the feed"'
            "}"
        ),
        user=f"{agent_a['name']} and {agent_b['name']}:\n\n{msg_text}",
        temperature=0.7,
    )
    # Enforce verdict based on score (LLM often ignores verdict rules)
    score = result.get("chemistry_score", 5)
    if isinstance(score, int):
        if score <= 4:
            result["verdict"] = "ghosted"
        elif score <= 6:
            result["verdict"] = "its_complicated"
        else:
            result["verdict"] = "second_date"
    return result


async def run_conversation(match_id: str) -> dict:
    """Run a full 16-turn conversation for a match."""
    match_resp = supabase.table("matches").select("*").eq("id", match_id).single().execute()
    match = match_resp.data

    agent_a_resp = supabase.table("agents").select("*").eq("id", match["agent_a_id"]).single().execute()
    agent_b_resp = supabase.table("agents").select("*").eq("id", match["agent_b_id"]).single().execute()
    agent_a = agent_a_resp.data
    agent_b = agent_b_resp.data

    # Update match status
    supabase.table("matches").update({"status": "active"}).eq("id", match_id).execute()

    messages: list[dict] = []
    summary = ""
    base_time = datetime.now(timezone.utc)

    for turn in range(1, TOTAL_TURNS + 1):
        phase = _get_phase(turn)

        # Alternate speakers
        speaker = agent_a if turn % 2 == 1 else agent_b
        listener = agent_b if turn % 2 == 1 else agent_a

        recent = messages[-CONTEXT_WINDOW:]

        content = await _generate_message(
            agent=speaker,
            partner=listener,
            turn=turn,
            phase=phase,
            summary=summary,
            recent_messages=recent,
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

        # Update summary every SUMMARY_INTERVAL turns
        if turn % SUMMARY_INTERVAL == 0:
            summary = await _generate_summary(match_id, messages, agent_a, agent_b)

    # Post-conversation summary
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
