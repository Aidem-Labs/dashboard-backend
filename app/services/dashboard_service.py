import httpx
from app.config import DASHBOARD_URL


async def identify_user_type(email: str) -> str:
    """Call the LMN8-Dashboard API to identify whether an email belongs to
    a patient, student, or neither.

    Returns "patient", "student", or "default".
    Failures always return "default" — never breaks chat.
    """
    if not email:
        return "default"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{DASHBOARD_URL}/api/internal/identify-user",
                json={"email": email},
            )

        if resp.status_code != 200:
            print(f"[DASHBOARD] identify-user returned {resp.status_code}")
            return "default"

        body = resp.json()
        return body.get("user_type", "default")

    except Exception as e:
        print(f"[DASHBOARD] identify-user error: {e}")
        return "default"
