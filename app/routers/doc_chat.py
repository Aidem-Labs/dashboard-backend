from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from uuid import UUID, uuid4
from app.models.schemas import ChatResponse
from app.agents.document_agent import build_ketamine_agent_graph
from app.db.database import get_pool

router = APIRouter(prefix="/api/doc-chat", tags=["doc-chat"])

ketamine_agent_graph = build_ketamine_agent_graph()


class PublicDocChatRequest(BaseModel):
    session_id: Optional[UUID] = None
    message: str


async def ensure_public_session(session_id: UUID) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            str(session_id),
        )


@router.post("")
async def doc_chat(request: PublicDocChatRequest):
    session_id = request.session_id or uuid4()
    await ensure_public_session(session_id)

    result = await ketamine_agent_graph.ainvoke({
        "session_id": str(session_id),
        "documents": [],
        "user_message": request.message,
        "assistant_reply": "",
        "safety_triggered": False,
        "sources": [],
    })

    return ChatResponse(
        session_id=str(session_id),
        response=result["assistant_reply"],
        personas=["Ketamine Therapy Assistant"],
        sources=result.get("sources", []),
    )
