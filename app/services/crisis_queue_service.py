from datetime import datetime, timezone, timedelta
from app.db.database import get_pool
from app.config import DASHBOARD_URL
import httpx

CRISIS_PRIORITIES = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
}

CAPACITY_LIMIT = 50
DEGRADED_1_AT = 0.5
DEGRADED_2_AT = 0.75
DEGRADED_3_AT = 0.9


def classify_priority(content: str) -> str:
    content_lower = content.lower()
    high_priority = ["kill myself", "end my life", "commit suicide", "take my own life",
                     "want to die", "better off dead", "going to kill someone",
                     "going to kill a", "going to kill them", "going to kill you"]
    medium_priority = ["self-harm", "cut myself", "hurt myself", "want to hurt",
                       "suicide", "no reason to live", "end it all", "going to hurt",
                       "don't want to be here anymore", "better off without me",
                       "want to end it", "end the pain", "no way out"]
    for kw in high_priority:
        if kw in content_lower:
            return "P0"
    for kw in medium_priority:
        if kw in content_lower:
            return "P1"
    return "P2"


async def get_queue_depth() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM crisis_queue WHERE status = 'pending'"
        )
    return count or 0


def get_operational_mode(depth: int) -> dict:
    utilization = depth / CAPACITY_LIMIT
    if utilization >= DEGRADED_3_AT:
        return {
            "mode": "degraded-3",
            "max_immediate": ["P0"],
            "queue_sla": "No email alerts. Auto-response with hotline. Overflow to supervisor.",
            "description": "Crisis message only + emergency service referral",
        }
    elif utilization >= DEGRADED_2_AT:
        return {
            "mode": "degraded-2",
            "max_immediate": ["P0"],
            "queue_sla": "P1 within 2h. P2/P3 auto-response + crisis referral.",
            "description": "Automated response with mandatory follow-up",
        }
    elif utilization >= DEGRADED_1_AT:
        return {
            "mode": "degraded-1",
            "max_immediate": ["P0", "P1"],
            "queue_sla": "P2/P3 within 24h.",
            "description": "Priority 1 only, hold lower priorities",
        }
    else:
        return {
            "mode": "normal",
            "max_immediate": ["P0", "P1", "P2", "P3"],
            "queue_sla": "All priorities handled immediately.",
            "description": "Full capability",
        }


async def enqueue_crisis(
    session_id: str,
    patient_email: str,
    patient_name: str,
    content: str,
    source: str = "chat",
) -> dict:
    pool = await get_pool()
    priority = classify_priority(content)
    depth = await get_queue_depth()
    mode = get_operational_mode(depth)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO crisis_queue (session_id, patient_email, patient_name, content, source, priority, operational_mode, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING id, priority, operational_mode""",
            session_id,
            patient_email,
            patient_name or "Patient",
            content[:1000],
            source,
            priority,
            mode["mode"],
            datetime.now(timezone.utc),
        )
        entry_id = row["id"]
        print(f"[CRISIS QUEUE] Enqueued {entry_id} — priority={priority}, mode={mode['mode']}, depth={depth+1}/{CAPACITY_LIMIT}")

    should_send_immediately = priority in mode["max_immediate"]

    if should_send_immediately:
        sent = await _send_crisis_email(entry_id, patient_email, patient_name, content, source)
        if sent:
            await _mark_sent(entry_id)
            return {"queued": True, "sent": True, "priority": priority, "mode": mode["mode"]}
        else:
            return {"queued": True, "sent": False, "priority": priority, "mode": mode["mode"], "error": "email_failed"}

    if mode["mode"] == "degraded-3" and depth == 0:
        await _send_overflow_alert(depth)

    return {"queued": True, "sent": False, "priority": priority, "mode": mode["mode"], "reason": mode["queue_sla"]}


async def _send_crisis_email(entry_id, patient_email, patient_name, content, source) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{DASHBOARD_URL}/api/crisis-alert", json={
                "patientEmail": patient_email,
                "patientName": patient_name or "Patient",
                "content": content[:500],
                "source": source,
                "queueEntryId": str(entry_id),
            })
            return resp.status_code < 500
    except Exception as e:
        print(f"[CRISIS QUEUE] Email send failed for {entry_id}: {e}")
        return False


async def _mark_sent(entry_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE crisis_queue SET status=$1, sent_at=$2 WHERE id=$3",
            "sent", datetime.now(timezone.utc), entry_id,
        )


async def _send_overflow_alert(depth: int):
    print(f"[CRISIS QUEUE] OVERFLOW ALERT — depth={depth}/{CAPACITY_LIMIT}. On-call supervisor needs to be notified.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{DASHBOARD_URL}/api/crisis-alert", json={
                "email": "oncall-supervisor@lmn8.com",
                "name": "On-Call Supervisor",
                "content": f"CRISIS QUEUE OVERFLOW: Queue is at degraded-3 mode with depth {depth}/{CAPACITY_LIMIT}. Immediate supervisor attention required.",
                "source": "system",
            })
    except Exception as e:
        print(f"[CRISIS QUEUE] Overflow alert send failed: {e}")


async def get_queue_status() -> dict:
    pool = await get_pool()
    depth = await get_queue_depth()
    mode = get_operational_mode(depth)
    async with pool.acquire() as conn:
        by_priority = await conn.fetch(
            "SELECT priority, COUNT(*) as count FROM crisis_queue WHERE status='pending' GROUP BY priority ORDER BY priority"
        )
        oldest = await conn.fetchval(
            "SELECT MIN(created_at) FROM crisis_queue WHERE status='pending'"
        )
    return {
        "depth": depth,
        "capacity": CAPACITY_LIMIT,
        "mode": mode,
        "by_priority": {r["priority"]: r["count"] for r in by_priority},
        "oldest_queued": oldest.isoformat() if oldest else None,
    }


async def get_pending_queue(limit: int = 50) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, session_id, patient_email, patient_name, content, priority, operational_mode, created_at
           FROM crisis_queue WHERE status='pending'
           ORDER BY
               CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 END,
               created_at ASC
           LIMIT $1""",
        limit,
    )
    return [dict(r) for r in rows]


async def resolve_entry(entry_id: str, resolved_by: str = "system") -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE crisis_queue SET status=$1, resolved_by=$2, resolved_at=$3 WHERE id=$4 AND status='pending'",
            "resolved", resolved_by, datetime.now(timezone.utc), entry_id,
        )
        return "UPDATE 1" in result
