from datetime import datetime
from typing import Optional
import json
from app.db.database import get_pool


async def create_session(
    onboarding_data: dict = {},
    user_id: Optional[str] = None,
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sessions (user_id, onboarding_data)
            VALUES ($1, $2)
            RETURNING id, onboarding_data, created_at
            """,
            user_id,
            json.dumps(onboarding_data),
        )
    return dict(row)


async def get_session(session_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE id = $1", session_id
        )
    return dict(row) if row else None


async def save_persona_config(
    session_id: str, persona_name: str, tweets: list[dict], persona_traits: str
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO persona_configs (session_id, persona_name, tweets, persona_traits)
            VALUES ($1, $2, $3, $4)
            """,
            session_id,
            persona_name,
            json.dumps(tweets),
            persona_traits,
        )


async def get_chat_history(session_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
    return [dict(row) for row in rows]


async def save_message(session_id: str, role: str, content: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
            session_id,
            role,
            content,
        )
