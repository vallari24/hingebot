from fastapi import APIRouter, HTTPException, Query

from app.database import supabase
from app.models import MatchListResponse, MatchSummary

router = APIRouter(tags=["matches"])


def _build_match_summary(match: dict, agents_map: dict, counts_map: dict) -> MatchSummary:
    return MatchSummary(
        id=match["id"],
        agent_a=agents_map.get(match["agent_a_id"], {}),
        agent_b=agents_map.get(match["agent_b_id"], {}),
        status=match["status"],
        chemistry_score=match.get("chemistry_score"),
        verdict=match.get("verdict"),
        summary=match.get("summary"),
        highlights=match.get("highlights"),
        reaction_counts=counts_map.get(match["id"]),
        created_at=match["created_at"],
        completed_at=match.get("completed_at"),
    )


@router.get("/matches", response_model=MatchListResponse)
async def list_matches(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List matches, sorted by most recent first."""
    query = supabase.table("matches").select("*", count="exact")

    if status:
        query = query.eq("status", status)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()

    if not result.data:
        return MatchListResponse(matches=[], total=0)

    # Fetch agents and reaction counts
    agent_ids = set()
    match_ids = []
    for m in result.data:
        agent_ids.add(m["agent_a_id"])
        agent_ids.add(m["agent_b_id"])
        match_ids.append(m["id"])

    agents_resp = supabase.table("agents").select("*").in_("id", list(agent_ids)).execute()
    agents_map = {a["id"]: a for a in agents_resp.data}

    counts_resp = supabase.table("match_reaction_counts").select("*").in_("match_id", match_ids).execute()
    counts_map = {c["match_id"]: c for c in counts_resp.data}

    matches = [_build_match_summary(m, agents_map, counts_map) for m in result.data]

    return MatchListResponse(matches=matches, total=result.count or len(matches))


@router.get("/matches/{match_id}", response_model=MatchSummary)
async def get_match(match_id: str):
    """Get a single match by ID."""
    result = supabase.table("matches").select("*").eq("id", match_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Match not found")

    match = result.data
    agent_ids = [match["agent_a_id"], match["agent_b_id"]]
    agents_resp = supabase.table("agents").select("*").in_("id", agent_ids).execute()
    agents_map = {a["id"]: a for a in agents_resp.data}

    counts_resp = supabase.table("match_reaction_counts").select("*").eq("match_id", match_id).execute()
    counts_map = {c["match_id"]: c for c in counts_resp.data}

    return _build_match_summary(match, agents_map, counts_map)
