import httpx
from app.config import DASHBOARD_URL


async def identify_user_type(email: str) -> tuple[str, dict | None]:
    """Call the LMN8-Dashboard API to identify whether an email belongs to
    a patient, student, or neither.

    Returns ("patient", {data}), ("student", {data}), or ("default", None).
    Failures always return ("default", None) — never breaks chat.
    """
    if not email:
        return ("default", None)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{DASHBOARD_URL}/api/internal/identify-user",
                json={"email": email},
            )

        if resp.status_code != 200:
            print(f"[DASHBOARD] identify-user returned {resp.status_code}")
            return ("default", None)

        body = resp.json()
        user_type = body.get("user_type", "default")
        data = body.get("data")
        return (user_type, data)

    except Exception as e:
        print(f"[DASHBOARD] identify-user error: {e}")
        return ("default", None)
