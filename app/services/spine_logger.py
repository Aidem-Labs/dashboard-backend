from app.db.database import get_pool


async def log_to_spine(
    session_id: str,
    trigger_type: str,
    original_output: str,
    replacement_output: str,
):
    """Log a bias-drift event to the spine_log table for audit."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO spine_log (session_id, trigger_type, original_output, replacement_output)
                   VALUES ($1, $2, $3, $4)""",
                session_id,
                trigger_type,
                original_output[:1000],
                replacement_output[:1000],
            )
        print(f"[SPINE] Logged {trigger_type} for session {session_id[:8]}...")
    except Exception as e:
        print(f"[SPINE] Failed to log: {e}")
