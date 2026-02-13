from openai import AsyncOpenAI

from app.config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

MODEL = "gpt-4o-mini"


async def complete(system: str, user: str, temperature: float = 0.9, max_tokens: int = 512) -> str:
    response = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def complete_json(system: str, user: str, temperature: float = 0.7) -> dict:
    response = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    import json
    return json.loads(response.choices[0].message.content or "{}")
