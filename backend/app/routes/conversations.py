from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database import supabase
from app.models import ConversationResponse, Message

router = APIRouter(tags=["conversations"])


@router.get("/matches/{match_id}/messages", response_model=ConversationResponse)
async def get_conversation(
    match_id: str,
    include_unrevealed: bool = Query(False, description="Include messages not yet revealed"),
):
    """Get all messages for a match conversation."""
    # Fetch match
    match_resp = supabase.table("matches").select("*").eq("id", match_id).single().execute()
    if not match_resp.data:
        raise HTTPException(status_code=404, detail="Match not found")
    match = match_resp.data

    # Fetch agents
    agent_ids = [match["agent_a_id"], match["agent_b_id"]]
    agents_resp = supabase.table("agents").select("*").in_("id", agent_ids).execute()
    agents_map = {a["id"]: a for a in agents_resp.data}

    # Fetch messages
    msg_query = (
        supabase.table("messages")
        .select("*")
        .eq("match_id", match_id)
        .order("turn_number")
    )

    if not include_unrevealed:
        now = datetime.now(timezone.utc).isoformat()
        msg_query = msg_query.lte("reveal_at", now)

    msg_resp = msg_query.execute()

    messages = []
    for m in msg_resp.data:
        agent = agents_map.get(m["agent_id"], {})
        messages.append(Message(
            id=m["id"],
            match_id=m["match_id"],
            agent_id=m["agent_id"],
            agent_name=agent.get("name", "Unknown"),
            content=m["content"],
            turn_number=m["turn_number"],
            phase=m["phase"],
            reveal_at=m["reveal_at"],
            created_at=m["created_at"],
        ))

    # Build match summary
    counts_resp = supabase.table("match_reaction_counts").select("*").eq("match_id", match_id).execute()
    counts_map = {c["match_id"]: c for c in counts_resp.data}

    from app.routes.matches import _build_match_summary
    match_summary = _build_match_summary(match, agents_map, counts_map)

    return ConversationResponse(match=match_summary, messages=messages)
