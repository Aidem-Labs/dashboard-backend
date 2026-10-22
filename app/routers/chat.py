import json
import re
from uuid import UUID
from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.agents.persona_agent import build_agent_graph
from app.services import session_service


UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I
)


def _is_valid_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match(value))

router = APIRouter(prefix="/api", tags=["chat"])

# Build the agent graph once
agent_graph = build_agent_graph()


def _extract_personas(onboarding_data: dict) -> list[str]:
    """Extract persona names from onboarding answers."""
    personas = []
    inspiration = onboarding_data.get("inspirationFigure", "")
    actor_author = onboarding_data.get("actorAuthorStyle", "")

    if inspiration:
        # Take first name before any comma or parenthesis
        name = inspiration.split(",")[0].split("(")[0].strip()
        if name:
            personas.append(name)
    if actor_author:
        name = actor_author.split(",")[0].split("(")[0].strip()
        if name:
            personas.append(name)

    # Remove duplicates
    seen = set()
    personas = [p for p in personas if not (p.lower() in seen or seen.add(p.lower()))]
    return personas if personas else ["Assistant"]


def _build_user_context(onboarding_data: dict) -> str:
    """Build user context string from onboarding answers for the agent."""
    if not onboarding_data:
        return ""

    mapping = {
        "inspirationFigure": "Person they look up to",
        "inspirationQuality": "What they admire about that person",
        "actorAuthorStyle": "Actors/authors whose style resonates",
        "actorAuthorTone": "What connects with them about that style",
        "spiritualPractices": "Spiritual practices or values important to them",
        "spiritualReflection": "How they want their companion to honor that",
        "lifeLandscape": "How their current life chapter feels (metaphor)",
        "safePlace": "What a safe place looks like for them",
        "strengthSymbol": "A symbol of strength or peace for them",
        "sensoryAnchor": "Sounds, colors, textures that ground them",
        "chapterTitle": "Title they'd give this chapter of their life",
        "strengthMoment": "A recent moment they felt their best",
        "primaryHope": "Biggest shift or hope for this journey",
        "copingPattern": "What they do when feeling overwhelmed",
    }

    context_parts = ["USER CONTEXT (from onboarding):"]
    for key, label in mapping.items():
        value = onboarding_data.get(key)
        if value:
            context_parts.append(f"- {label}: {value}")

    return "\n".join(context_parts)


@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message and get a persona-based response. Public endpoint (no auth)."""
    print("\n" + "="*80)
    print("CHAT ENDPOINT HIT - STARTING AGENT WORKFLOW")
    print("="*80)
    print(f"Session ID: {request.session_id}")
    print(f"User message: {request.message}")
    print("Fetching session and initializing agent...")
    
    # Get session to know about user
    session = None
    if _is_valid_uuid(request.session_id):
        session = await session_service.get_session(request.session_id)

    # If session doesn't exist but onboarding_data is provided, create one on the fly
    if not session:
        if request.onboarding_data:
            session = await session_service.create_session(
                onboarding_data=request.onboarding_data,
                user_id=None,
            )
            # Re-fetch so we have the full row
            session = await session_service.get_session(str(session["id"]))
        if not session:
            return {"error": "Session not found"}

    onboarding_data = session.get("onboarding_data", {}) or {}
    if isinstance(onboarding_data, str):
        try:
            onboarding_data = json.loads(onboarding_data)
        except (json.JSONDecodeError, TypeError):
            onboarding_data = {}

    # Extract personas from onboarding answers
    personas = _extract_personas(onboarding_data)
    
    # Build user context for the agent
    user_context = _build_user_context(onboarding_data)

    if request.memory_context:
        user_context = user_context + "\n\n" + request.memory_context[:2400]
        print("Long-term memory loaded from previous sessions")

    print(f"Active personas: {', '.join(personas)}")
    if user_context:
        print(f"User context loaded from onboarding")
    print("="*80)

    # Run the agent graph
    print("\nRunning LangGraph agent workflow...")
    actual_session_id = session["id"] if isinstance(session, dict) else request.session_id
    result = await agent_graph.ainvoke({
        "session_id": str(actual_session_id),
        "personas": personas,
        "stored_profiles": [],
        "tweets": [],
        "user_message": request.message,
        "assistant_reply": "",
        "user_context": user_context,
    })
    
    print("\n" + "="*80)
    print("CHAT WORKFLOW COMPLETED SUCCESSFULLY")
    print(f"Response length: {len(result['assistant_reply'])} characters")
    print("="*80 + "\n")

    return ChatResponse(
        session_id=str(actual_session_id),
        response=result["assistant_reply"],
        personas=personas,
    )
