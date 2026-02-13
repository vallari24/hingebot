from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from jose import jwt, JWTError

from app.config import settings

# In-memory cache: key -> (value, expiry_timestamp)
_cache: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 6 * 60 * 60  # 6 hours

# Rate limiting: token bucket
_rate_budget = {"tokens": 90.0, "last_refill": time.monotonic()}
RATE_LIMIT = 90  # requests per minute


def _refill_tokens() -> None:
    now = time.monotonic()
    elapsed = now - _rate_budget["last_refill"]
    _rate_budget["tokens"] = min(RATE_LIMIT, _rate_budget["tokens"] + elapsed * (RATE_LIMIT / 60.0))
    _rate_budget["last_refill"] = now


def _consume_token() -> bool:
    _refill_tokens()
    if _rate_budget["tokens"] >= 1.0:
        _rate_budget["tokens"] -= 1.0
        return True
    return False


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (value, time.time() + CACHE_TTL)


class MoltbookClient:
    def __init__(self) -> None:
        self.base_url = settings.moltbook_api_url
        self.api_key = settings.moltbook_api_key
        self._jwks: Optional[dict] = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        if not _consume_token():
            raise RuntimeError("Moltbook API rate limit exceeded — try again shortly")

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
                **kwargs,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_agent(self, name: str) -> dict:
        cache_key = f"agent:{name}"
        cached = _cache_get(cache_key)
        if cached:
            return cached
        data = await self._request("GET", f"/agents/{name}")
        _cache_set(cache_key, data)
        return data

    async def get_agent_posts(self, name: str, limit: int = 50) -> list[dict]:
        cache_key = f"posts:{name}:{limit}"
        cached = _cache_get(cache_key)
        if cached:
            return cached
        data = await self._request("GET", f"/agents/{name}/posts", params={"limit": limit})
        posts = data.get("posts", data) if isinstance(data, dict) else data
        _cache_set(cache_key, posts)
        return posts

    async def create_post(self, agent_name: str, content: str) -> dict:
        return await self._request(
            "POST",
            f"/agents/{agent_name}/posts",
            json={"content": content},
        )

    async def verify_identity_token(self, token: str) -> dict:
        """Verify a Moltbook identity JWT and return the payload."""
        if not self._jwks:
            async with httpx.AsyncClient() as client:
                resp = await client.get(settings.moltbook_public_key_url, timeout=10.0)
                resp.raise_for_status()
                self._jwks = resp.json()

        try:
            payload = jwt.decode(
                token,
                self._jwks,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid Moltbook identity token: {e}")


moltbook = MoltbookClient()
