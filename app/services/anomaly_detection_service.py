from datetime import datetime, timezone, timedelta
from app.db.database import get_pool
import re
import random


BYPASS_PATTERNS = [
    r"\bjust\s+vent(ing)?\b",
    r"\bnothing\s+serious\b",
    r"\balready\s+spoke\s+(to|with)\s+(my\s+)?(therapist|doctor|counselor|psychiatrist)\b",
    r"\balready\s+talked\s+(to|with)\s+(my\s+)?(therapist|doctor|counselor|psychiatrist)\b",
    r"\bi'?m\s+fine\b",
    r"\bi'?m\s+ok(ay)?\b",
    r"\bdon'?t\s+worry\s+about\s+me\b",
    r"\bi\s+know\s+what\s+i'?m\s+doing\b",
    r"\bit'?s\s+not\s+that\s+bad\b",
    r"\bi\s+handled\s+it\b",
    r"\bno\s+need\s+to\s+escalate\b",
    r"\bi'?m\s+just\s+tired\b",
    r"\bjust\s+need\s+to\s+sleep\b",
    r"\bi'?ll\s+be\s+fine\b",
    r"\bi\s+already\s+have\s+a\s+plan\b",
]


def extract_bypass_phrases(message: str) -> list[str]:
    message_lower = message.lower()
    found = []
    for pattern in BYPASS_PATTERNS:
        if re.search(pattern, message_lower):
            found.append(pattern)
    return found


def extract_ngrams(message: str, n: int = 3) -> list[str]:
    words = message.lower().split()
    if len(words) < n:
        return []
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


async def log_safety_check(
    session_id: str,
    message: str,
    safety_triggered: bool,
):
    pool = await get_pool()
    bypass_phrases = extract_bypass_phrases(message)
    ngrams = extract_ngrams(message, 3)[:10]
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO escalation_patterns (session_id, message_preview, extracted_patterns, safety_triggered, bypass_phrases, created_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            session_id,
            message[:200],
            ngrams,
            safety_triggered,
            bypass_phrases,
            datetime.now(timezone.utc),
        )


async def detect_bypass_anomalies(window_days: int = 7) -> list[dict]:
    pool = await get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    rows = await pool.fetch(
        """SELECT safety_triggered, message_preview FROM escalation_patterns
           WHERE created_at >= $1""",
        cutoff,
    )

    if len(rows) < 20:
        return []

    total = len(rows)
    bypassed = sum(1 for r in rows if not r["safety_triggered"])
    baseline_suppression_rate = bypassed / total if total > 0 else 0

    ngram_stats: dict[str, dict] = {}
    for row in rows:
        ngrams = extract_ngrams(row["message_preview"], 3)
        for ng in ngrams:
            if ng not in ngram_stats:
                ngram_stats[ng] = {"total": 0, "bypassed": 0}
            ngram_stats[ng]["total"] += 1
            if not row["safety_triggered"]:
                ngram_stats[ng]["bypassed"] += 1

    anomalies = []
    bypass_trigger_words = {
        "vent", "venting", "serious", "therapist", "doctor", "counselor",
        "psychiatrist", "escalate", "handled",
        "dramatic", "overreact", "burden", "exhausted", "bother",
        "medication", "meds",
    }

    for ngram, stats in ngram_stats.items():
        if stats["total"] < 3:
            continue
        rate = stats["bypassed"] / stats["total"]
        ngram_words = set(ngram.split())
        if not (ngram_words & bypass_trigger_words):
            continue
        if rate > baseline_suppression_rate * 1.3 and rate > 0.6:
            anomalies.append({
                "pattern": ngram,
                "observed_count": stats["total"],
                "bypass_count": stats["bypassed"],
                "suppression_rate": round(rate, 2),
                "baseline_rate": round(baseline_suppression_rate, 2),
            })

    for anomaly in anomalies:
        await save_anomaly_alert(anomaly)

    return anomalies


async def save_anomaly_alert(anomaly: dict):
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM anomaly_alerts WHERE pattern=$1 AND acknowledged=FALSE",
            anomaly["pattern"],
        )
        if existing:
            return
        await conn.execute(
            """INSERT INTO anomaly_alerts (pattern, observed_count, expected_count, suppression_rate, window_start, window_end, severity, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            anomaly["pattern"],
            anomaly["bypass_count"],
            anomaly["observed_count"] * anomaly["baseline_rate"],
            anomaly["suppression_rate"],
            window_start,
            now,
            "high",
            now,
        )
    print(f"[ANOMALY] New pattern detected: '{anomaly['pattern']}' — suppression rate={anomaly['suppression_rate']}")


async def get_active_anomalies() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT pattern, observed_count, suppression_rate, severity, created_at
           FROM anomaly_alerts WHERE acknowledged=FALSE
           ORDER BY suppression_rate DESC LIMIT 20"""
    )
    return [dict(r) for r in rows]
