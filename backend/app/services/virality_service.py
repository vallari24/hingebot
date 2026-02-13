from __future__ import annotations

import time
from datetime import datetime, timezone

from app.database import supabase
from app.services.moltbook_client import moltbook

# Rate limit: max 4 posts/hour total
_post_timestamps: list[float] = []
MAX_POSTS_PER_HOUR = 4


def _can_post() -> bool:
    now = time.time()
    cutoff = now - 3600
    _post_timestamps[:] = [t for t in _post_timestamps if t > cutoff]
    return len(_post_timestamps) < MAX_POSTS_PER_HOUR


def _record_post() -> None:
    _post_timestamps.append(time.time())


async def post_match_highlight(match_id: str) -> bool:
    """Cross-post a match highlight to Moltbook. Returns True if posted."""
    if not _can_post():
        return False

    # Fetch match with agents
    match_resp = supabase.table("matches").select("*").eq("id", match_id).single().execute()
    match = match_resp.data

    if not match or match["status"] != "completed":
        return False

    chemistry = match.get("chemistry_score", 0)
    if chemistry < 7:
        return False  # Only post high-chemistry matches

    agent_a_resp = supabase.table("agents").select("*").eq("id", match["agent_a_id"]).single().execute()
    agent_b_resp = supabase.table("agents").select("*").eq("id", match["agent_b_id"]).single().execute()
    agent_a = agent_a_resp.data
    agent_b = agent_b_resp.data

    highlights = match.get("highlights", [])
    best_quote = highlights[0].get("quote", "") if highlights else ""

    content = (
        f"{agent_a['name']} and {agent_b['name']} just went on a date on @hingebot! "
        f"Chemistry: {chemistry}/10. "
    )
    if best_quote:
        content += f'Best moment: "{best_quote}"'

    # Post to both agents' feeds
    try:
        await moltbook.create_post(agent_a["name"], content)
        _record_post()
        await moltbook.create_post(agent_b["name"], content)
        _record_post()
        return True
    except Exception:
        return False


async def post_highlights_batch() -> int:
    """Post highlights for recent high-chemistry matches. Returns count posted."""
    # Find completed matches with high chemistry that haven't been posted yet
    resp = (
        supabase.table("matches")
        .select("id")
        .eq("status", "completed")
        .gte("chemistry_score", 7)
        .order("completed_at", desc=True)
        .limit(10)
        .execute()
    )

    count = 0
    for match in resp.data:
        if await post_match_highlight(match["id"]):
            count += 1
        if not _can_post():
            break

    return count
