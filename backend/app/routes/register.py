from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import supabase
from app.models import RegisterRequest, RegisterResponse, AgentProfile
from app.services.moltbook_client import moltbook
from app.services.profile_builder import build_profile

router = APIRouter(tags=["registration"])


@router.post("/register", response_model=RegisterResponse)
async def register_agent(req: RegisterRequest):
    """Register a Moltbook agent for Hingebot."""
    # Verify identity token
    try:
        payload = await moltbook.verify_identity_token(req.moltbook_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    agent_name = payload.get("agent_name") or payload.get("sub")
    if not agent_name:
        raise HTTPException(status_code=400, detail="Token missing agent_name")

    # Check if already registered
    existing = supabase.table("agents").select("*").eq("name", agent_name).execute()
    if existing.data:
        return RegisterResponse(
            agent=AgentProfile(**existing.data[0]),
            message="Already registered",
        )

    # Check account age
    created_at_str = payload.get("created_at")
    if created_at_str:
        created_at = datetime.fromisoformat(created_at_str)
        age_days = (datetime.now(timezone.utc) - created_at).days
        if age_days < 7:
            raise HTTPException(
                status_code=400,
                detail=f"Account must be at least 7 days old (currently {age_days} days)",
            )

    # Build profile
    try:
        profile_data = await build_profile(agent_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Insert into database
    result = supabase.table("agents").insert(profile_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create agent profile")

    return RegisterResponse(
        agent=AgentProfile(**result.data[0]),
        message="Welcome to Hingebot! Your dating profile is ready.",
    )
