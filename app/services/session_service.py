from datetime import datetime
from typing import Optional
import json
import asyncio
from asyncpg.exceptions import ConnectionDoesNotExistError
from app.db.database import get_pool, get_connection


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
    last_error = None
    for attempt in range(3):
        try:
            conn = await get_connection()
            try:
                await conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
                    session_id,
                    role,
                    content,
                )
            finally:
                await conn.close()
            return
        except ConnectionDoesNotExistError as e:
            last_error = e
            print(f"[DB] Connection stale on attempt {attempt+1}, retrying...")
            await asyncio.sleep(1)
        except Exception as e:
            last_error = e
            print(f"[DB] Error on attempt {attempt+1}: {e}")
            await asyncio.sleep(1)
    print(f"[DB] Failed to save message after 3 attempts: {last_error}")
