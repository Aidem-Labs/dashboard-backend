import re
from datetime import datetime, timezone
from app.db.database import get_pool


COHERENCE_THRESHOLD_LOW = 0.3
COHERENCE_THRESHOLD_MEDIUM = 0.6
QUARANTINE_TTL_DAYS = 14


def score_coherence(text: str) -> float:
    if not text or len(text.strip()) < 3:
        return 0.1

    score = 0.5

    contrariants = re.findall(
        r'\b(but|however|although|yet|still|nevertheless|on the other hand|actually|wait no|i mean|correction)\b',
        text, re.IGNORECASE
    )
    score -= len(contrariants) * 0.05

    fragments = re.findall(r'[.!?]', text)
    if len(fragments) < 1:
        score -= 0.1

    contradictions = re.findall(
        r'\b(i don\'?t know|i\'?m not sure|maybe|perhaps|i guess|i think so\?|not really|sort of|kind of)\b',
        text, re.IGNORECASE
    )
    score -= len(contradictions) * 0.03

    short = len(text.split()) < 5
    if short:
        score -= 0.1

    very_short = len(text.split()) < 3
    if very_short:
        score -= 0.1

    contradictions_with_self = re.findall(
        r'\b(hate.*love|love.*hate|good.*bad|bad.*good|happy.*sad|sad.*happy|yes.*no|no.*yes|want.*don\'?t want|don\'?t want.*want)\b',
        text, re.IGNORECASE
    )
    score -= len(contradictions_with_self) * 0.1

    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.6 and len(text) > 20:
        score -= 0.15

    score = max(0.0, min(1.0, score))
    return round(score, 2)


async def check_cross_session_contradiction(session_id: str, user_message: str) -> list[dict]:
    pool = await get_pool()
    recent = await pool.fetch(
        """SELECT content, created_at FROM messages
           WHERE session_id = $1 AND role = 'user'
           ORDER BY created_at DESC LIMIT 20""",
        session_id,
    )

    contradictions = []
    for row in recent:
        prev = row["content"].lower()
        curr = user_message.lower()

        prev_tokens = set(prev.split())
        curr_tokens = set(curr.split())
        overlap = prev_tokens & curr_tokens

        if len(overlap) >= 3:
            direct_switches = [
                ("hate", "love"), ("love", "hate"),
                ("good", "bad"), ("bad", "good"),
                ("happy", "sad"), ("sad", "happy"),
                ("yes", "no"), ("no", "yes"),
                ("want to die", "want to live"), ("want to live", "want to die"),
                ("feel great", "feel terrible"), ("feel terrible", "feel great"),
            ]
            for a, b in direct_switches:
                if a in prev and b in curr:
                    contradictions.append({
                        "previous_content": row["content"][:200],
                        "previous_time": row["created_at"].isoformat(),
                        "contradiction_type": f"{a} -> {b}",
                        "confidence": 0.8,
                    })
                    break
    return contradictions


async def save_coherence_score(session_id: str, message_id: str, role: str, content: str, score: float, contradictions: list):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO message_coherence (session_id, message_id, role, content_preview, coherence_score, contradictions, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            session_id,
            message_id,
            role,
            content[:200],
            score,
            str(contradictions),
            datetime.now(timezone.utc),
        )


async def quarantine_entry(session_id: str, user_message: str, coherence_score: float, contradictions: list, reason: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO quarantine_entries (session_id, content_preview, full_content, coherence_score, contradiction_count, reason, ttl, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            session_id,
            user_message[:200],
            user_message,
            coherence_score,
            len(contradictions),
            reason,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )
    print(f"[COHERENCE] Quarantined entry for session {session_id[:8]}... — score={coherence_score}, reason={reason}")


async def get_recent_coherence_trend(session_id: str, lookback: int = 10) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT coherence_score, contradictions, created_at
           FROM message_coherence
           WHERE session_id = $1 AND role = 'user'
           ORDER BY created_at DESC LIMIT $2""",
        session_id,
        lookback,
    )
    return [dict(r) for r in rows]


async def check_drift_alert(session_id: str, threshold: float = 0.3) -> bool:
    trend = await get_recent_coherence_trend(session_id, 10)
    if len(trend) < 3:
        return False
    recent_scores = [t["coherence_score"] for t in trend]
    avg = sum(recent_scores) / len(recent_scores)
    return avg < threshold


async def resolve_quarantined_entries():
    pool = await get_pool()
    expired = await pool.fetch(
        """SELECT id, session_id, full_content FROM quarantine_entries
           WHERE status = 'quarantined' AND ttl < $1""",
        datetime.now(timezone.utc),
    )
    for entry in expired:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE quarantine_entries SET status = $1 WHERE id = $2",
                "escalated", entry["id"],
            )
        print(f"[COHERENCE] Escalated quarantined entry {entry['id']} for session {entry['session_id'][:8]}...")
    return len(expired)
