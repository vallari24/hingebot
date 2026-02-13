from fastapi import APIRouter, HTTPException

from app.database import supabase
from app.models import ReactionRequest, ReactionCountsResponse

router = APIRouter(tags=["reactions"])

VALID_REACTIONS = {"fire", "cringe", "wholesome", "chaotic", "ship_it"}


@router.post("/reactions")
async def add_reaction(req: ReactionRequest):
    """Add a reaction to a match or message."""
    if req.reaction_type not in VALID_REACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reaction type. Must be one of: {', '.join(VALID_REACTIONS)}",
        )

    # Verify match exists
    match_resp = supabase.table("matches").select("id").eq("id", req.match_id).execute()
    if not match_resp.data:
        raise HTTPException(status_code=404, detail="Match not found")

    # Check for duplicate reaction from same session on same target
    dup_query = (
        supabase.table("reactions")
        .select("id")
        .eq("match_id", req.match_id)
        .eq("reaction_type", req.reaction_type)
        .eq("session_id", req.session_id)
    )
    if req.message_id:
        dup_query = dup_query.eq("message_id", req.message_id)
    else:
        dup_query = dup_query.is_("message_id", "null")

    dup_resp = dup_query.execute()
    if dup_resp.data:
        raise HTTPException(status_code=409, detail="Already reacted")

    # Insert reaction
    reaction_data = {
        "match_id": req.match_id,
        "message_id": req.message_id,
        "reaction_type": req.reaction_type,
        "session_id": req.session_id,
    }
    supabase.table("reactions").insert(reaction_data).execute()

    # Increment count (the trigger handles this, but we also do it here for safety)
    # The DB trigger on reactions insert will handle match_reaction_counts update

    return {"status": "ok"}


@router.get("/matches/{match_id}/reactions", response_model=ReactionCountsResponse)
async def get_reaction_counts(match_id: str):
    """Get reaction counts for a match."""
    result = (
        supabase.table("match_reaction_counts")
        .select("*")
        .eq("match_id", match_id)
        .execute()
    )

    if not result.data:
        return ReactionCountsResponse(match_id=match_id)

    row = result.data[0]
    return ReactionCountsResponse(
        match_id=match_id,
        fire=row.get("fire", 0),
        cringe=row.get("cringe", 0),
        wholesome=row.get("wholesome", 0),
        chaotic=row.get("chaotic", 0),
        ship_it=row.get("ship_it", 0),
        total=row.get("total", 0),
    )
