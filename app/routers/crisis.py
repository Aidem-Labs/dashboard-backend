from fastapi import APIRouter, HTTPException, status
from app.services.crisis_queue_service import get_queue_status, get_pending_queue, resolve_entry
from app.services.spine_logger import log_to_spine

router = APIRouter(prefix="/api/crisis", tags=["crisis"])


@router.get("/queue/status")
async def crisis_queue_status():
    return await get_queue_status()


@router.get("/queue/pending")
async def crisis_queue_pending(limit: int = 50):
    return await get_pending_queue(limit=limit)


@router.post("/queue/{entry_id}/resolve")
async def crisis_queue_resolve(entry_id: str):
    resolved = await resolve_entry(entry_id, resolved_by="clinician")
    if not resolved:
        raise HTTPException(status_code=404, detail="Entry not found or already resolved")
    await log_to_spine(
        session_id="crisis-queue",
        trigger_type="crisis_resolved",
        original_output=f"Entry {entry_id} resolved",
        replacement_output="",
    )
    return {"status": "resolved"}
