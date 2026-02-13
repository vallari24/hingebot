from fastapi import APIRouter

from app.models import TaskRunResponse
from app.services.matching_engine import run_matching_round
from app.services.conversation_engine import run_conversation
from app.services.virality_service import post_highlights_batch
from app.database import supabase

router = APIRouter(tags=["tasks"])


@router.post("/run-matches", response_model=TaskRunResponse)
async def run_matches():
    """Triggered by Cloud Scheduler every 2 hours. Runs a matching round."""
    matches = await run_matching_round(max_matches=20)
    return TaskRunResponse(
        status="ok",
        detail=f"Created {len(matches)} new matches",
        count=len(matches),
    )


@router.post("/run-conversations", response_model=TaskRunResponse)
async def run_conversations():
    """Process pending matches — run conversations for each."""
    pending = (
        supabase.table("matches")
        .select("id")
        .eq("status", "pending")
        .order("created_at")
        .limit(5)
        .execute()
    )

    count = 0
    for match in pending.data:
        await run_conversation(match["id"])
        count += 1

    return TaskRunResponse(
        status="ok",
        detail=f"Ran {count} conversations",
        count=count,
    )


@router.post("/post-highlights", response_model=TaskRunResponse)
async def post_highlights():
    """Post match highlights to Moltbook."""
    count = await post_highlights_batch()
    return TaskRunResponse(
        status="ok",
        detail=f"Posted {count} highlights to Moltbook",
        count=count,
    )
