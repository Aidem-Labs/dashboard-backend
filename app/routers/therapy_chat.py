import re
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from uuid import uuid4
from app.models.schemas import ChatResponse
from app.agents.document_agent import build_ketamine_agent_graph
from app.services.profile_service import get_multiple_celebrity_profiles
from app.services.tweet_service import fetch_celebrity_tweets
from app.services import session_service
from app.db.database import get_pool
from app.routers.chat import _extract_personas

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I
)

router = APIRouter(prefix="/api", tags=["therapy-chat"])

ketamine_graph = build_ketamine_agent_graph()


class TherapyChatRequest(BaseModel):
    session_id: str
    message: str
    onboarding_data: dict[str, Any] = {}
    user_context: dict[str, Any] = {}


def _build_persona_profile(personas: list[str], profiles: list[dict], tweets: list[dict]) -> str:
    """Build a communication style guide from persona data for the ketamine agent."""
    if not personas or personas == ["Assistant"]:
        return ""

    parts = []
    for profile in profiles:
        parts.append(f"User resonates with {profile['name']}.")
        parts.append(f"Communication style to mirror: {profile['speaking_style']}")
        parts.append(f"Personality traits to align with: {profile['personality_traits']}")
        parts.append(f"Topics that engage them: {profile['common_topics']}")

    if tweets:
        tweet_refs = "\n".join([f"  - \"{t['text']}\"" for t in tweets[:5]])
        parts.append(f"\nRecent references the user connects with:\n{tweet_refs}")

    parts.append("\nUse this style guide to adapt your tone and communication approach.")
    parts.append("Do NOT roleplay as the persona. You are the ketamine therapy guide.")
    parts.append("Use the style as a communication lens — the substance comes from your knowledge base.")

    return "\n".join(parts)


def _build_user_context_str(user_context: dict) -> str:
    """Build user context string from logged-in user info."""
    if not user_context:
        return ""
    parts = []
    name = user_context.get("name", "")
    disease = user_context.get("disease", "")
    goals = user_context.get("goals", "")
    if name:
        parts.append(f"User name: {name}")
    if disease:
        parts.append(f"User condition: {disease}")
    if goals:
        parts.append(f"User therapeutic goals: {goals}")
    return "\n".join(parts) if parts else ""


@router.post("/therapy-chat")
async def therapy_chat(request: TherapyChatRequest):
    print("\n" + "="*80)
    print("THERAPY CHAT ENDPOINT")
    print("="*80)
    print(f"Session: {request.session_id}, Message: {request.message[:50]}...")

    # 1. Ensure session exists (use UUID session_id or generate one)
    pool = await get_pool()
    actual_session_id = request.session_id if UUID_PATTERN.match(request.session_id) else str(uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            actual_session_id,
        )

    # 2. Run persona analysis (profiles + tweets) to build communication style guide
    personas = _extract_personas(request.onboarding_data)
    persona_profile = ""

    if personas and personas != ["Assistant"]:
        print(f"Running persona analysis for: {personas}")
        profiles = await get_multiple_celebrity_profiles(personas)
        all_tweets = []
        for persona in personas:
            tweets = await fetch_celebrity_tweets(persona, count=5)
            for t in tweets:
                t["persona"] = persona
            all_tweets.extend(tweets)
        persona_profile = _build_persona_profile(personas, profiles, all_tweets)
        print(f"Persona profile built ({len(persona_profile)} chars)")

    # 3. Build user context
    user_context_str = _build_user_context_str(request.user_context)
    if user_context_str:
        print(f"User context: {user_context_str}")

    # 4. Run ketamine agent with persona profile + user context
    print("Running ketamine agent...")
    result = await ketamine_graph.ainvoke({
        "session_id": actual_session_id,
        "documents": [],
        "user_message": request.message,
        "assistant_reply": "",
        "safety_triggered": False,
        "sources": [],
        "persona_profile": persona_profile,
        "user_context_str": user_context_str,
    })

    print(f"Response: {result['assistant_reply'][:80]}...")
    print("="*80)

    return ChatResponse(
        session_id=actual_session_id,
        response=result["assistant_reply"],
        personas=personas,
        sources=result.get("sources", []),
    )
