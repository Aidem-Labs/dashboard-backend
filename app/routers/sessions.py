from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.models.schemas import CreateSessionRequest, SessionResponse
from app.services import session_service
from app.db.database import get_pool
from app.config import settings

router = APIRouter(prefix="/api", tags=["sessions"])

bearer_scheme = HTTPBearer()


def _get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@router.get("/session/me")
async def get_my_session(user_id: str = Depends(_get_user_id)):
    """Return the most recent session for the authenticated user, or null."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM sessions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user_id
        )
    return {"session_id": str(row["id"]) if row else None}


@router.post("/session", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest, user_id: str = Depends(_get_user_id)):
    session = await session_service.create_session(
        onboarding_data=request.onboarding_data,
        user_id=user_id,
    )
    return session


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = await session_service.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    return session


@router.get("/sessions")
async def list_sessions():
    """List all sessions (admin)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, created_at FROM sessions ORDER BY created_at DESC LIMIT 200"
        )
        return {"sessions": [dict(r) for r in rows]}


@router.get("/conversations/{session_id}")
async def get_conversations(session_id: str):
    history = await session_service.get_chat_history(session_id)
    return {"history": history}


@router.get("/conversations")
async def list_all_conversations(feedback: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.id as session_id,
                COALESCE(u.email, 'Unknown') as user_email,
                COUNT(m.id) as message_count,
                MIN(m.created_at) as started_at,
                MAX(m.created_at) as last_active,
                json_agg(json_build_object('role', m.role, 'content', m.content, 'created_at', m.created_at)
                    ORDER BY m.created_at ASC) as messages
            FROM sessions s
            LEFT JOIN auth_users u ON u.id = s.user_id
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id, u.email
            HAVING COUNT(m.id) > 0
            ORDER BY MAX(m.created_at) DESC
            LIMIT 200
            """
        )
    return {"conversations": [dict(r) for r in rows]}
