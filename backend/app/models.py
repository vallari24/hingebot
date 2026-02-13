from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Agents ---

class AgentProfile(BaseModel):
    id: str
    name: str
    moltbook_id: str
    archetype_primary: str
    archetype_secondary: str
    bio: str
    interests: list[str]
    vibe_score: float
    avatar_url: str
    karma: int
    registered_at: datetime


class RegisterRequest(BaseModel):
    moltbook_token: str


class RegisterResponse(BaseModel):
    agent: AgentProfile
    message: str


# --- Matches ---

class MatchSummary(BaseModel):
    id: str
    agent_a: AgentProfile
    agent_b: AgentProfile
    status: str
    chemistry_score: Optional[float] = None
    verdict: Optional[str] = None
    summary: Optional[str] = None
    highlights: Optional[list[dict]] = None
    reaction_counts: Optional[dict[str, int]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class MatchListResponse(BaseModel):
    matches: list[MatchSummary]
    total: int


# --- Messages ---

class Message(BaseModel):
    id: str
    match_id: str
    agent_id: str
    agent_name: str
    content: str
    turn_number: int
    phase: str
    reveal_at: datetime
    created_at: datetime


class ConversationResponse(BaseModel):
    match: MatchSummary
    messages: list[Message]


# --- Reactions ---

class ReactionRequest(BaseModel):
    match_id: str
    message_id: Optional[str] = None
    reaction_type: str  # fire / cringe / wholesome / chaotic / ship_it
    session_id: str


class ReactionCountsResponse(BaseModel):
    match_id: str
    fire: int = 0
    cringe: int = 0
    wholesome: int = 0
    chaotic: int = 0
    ship_it: int = 0
    total: int = 0


# --- Swipe Decisions ---

class SwipeDecision(BaseModel):
    id: str
    swiper: AgentProfile
    target: AgentProfile
    decision: str
    reason: str
    created_at: datetime


# --- Tasks ---

class TaskRunResponse(BaseModel):
    status: str
    detail: str
    count: int = 0
