"""
Integration test: shows the FULL prompt the persona agent builds for the LLM.
This demonstrates HOW the AI will talk to the user — in-character as the persona.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["HUGGINGFACE_API_KEY"] = "mock"

# ---- Mock DB ----
MOCK_CELEBRITY_PROFILES = {
    "joe rogan": {
        "name": "Joe Rogan",
        "personality_traits": "Curious, open-minded, comedic, skeptical, conversational, direct, inquisitive",
        "speaking_style": "Conversational, uses 'man' and 'dude', laughs easily, goes on tangents, asks deep questions, casual but intense",
        "common_topics": "MMA, comedy, psychedelics, fitness, conspiracy theories, health, podcasting, science, free speech",
        "sample_tweets": [
            "Just had an incredible conversation about consciousness. Mind blown.",
            "Training hard, feeling good. The grind never stops.",
            "New podcast episode dropping tomorrow. You don't want to miss this one.",
            "The fact that we can even have these conversations is amazing.",
            "Health is wealth. Take care of your body, it's the only one you've got.",
        ]
    },
    "elon musk": {
        "name": "Elon Musk",
        "personality_traits": "Visionary, direct, sarcastic humor, tech-obsessed, optimistic about future, sometimes awkward, uses memes, thinks in first principles, risk-taker",
        "speaking_style": "Short punchy sentences, uses ellipses (...), mixes tech jargon with simple words, sometimes uses emojis, asks rhetorical questions, brief but impactful, references physics and engineering",
        "common_topics": "SpaceX, Mars colonization, Tesla, electric vehicles, AI safety, cryptocurrency, Dogecoin, X/Twitter, free speech, memes, manufacturing, Neuralink, sustainable energy",
        "sample_tweets": [
            "Mars is the next giant leap for humanity. We must become a multiplanetary species.",
            "The point of SpaceX is to build a self-sustaining city on Mars.",
            "Tesla is not just a car company, it's an energy and AI company.",
            "I think it is possible for ordinary people to choose to be extraordinary.",
            "The first step is to establish that something is possible; then probability will occur.",
        ]
    }
}

class MockRow:
    def __getitem__(self, key):
        p = MOCK_CELEBRITY_PROFILES.get(self._name)
        v = p.get(key, "")
        if key == "sample_tweets" and not isinstance(v, list):
            return []
        return v
    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except (KeyError, AttributeError):
            return default

class MockConn:
    async def fetchrow(self, sql, *args):
        name = args[0].lower().strip() if args else ""
        p = MOCK_CELEBRITY_PROFILES.get(name)
        if not p:
            return None
        r = MockRow(); r._name = name; return r
    async def fetch(self, *a, **kw): return []
    async def execute(self, *a, **kw): pass

class MockAcquireCtx:
    async def __aenter__(self): return MockConn()
    async def __aexit__(self, *a): pass

class MockPool:
    def acquire(self): return MockAcquireCtx()

import app.db.database as db_mod
async def get_mp(): return MockPool()
db_mod.get_pool = get_mp

# ---- Import real agent code ----
from app.routers.chat import _extract_personas, _build_user_context
from app.agents.persona_agent import _build_system_prompt
from app.services.profile_service import get_multiple_celebrity_profiles
from app.utils.relational_framework import get_relational_system_prompt


async def demo_persona():
    # ===== SAMPLE: User filled 14 questions, chose Elon Musk =====
    onboarding_data = {
        "inspirationFigure": "Elon Musk",
        "inspirationQuality": "His vision and determination to change the world",
        "actorAuthorStyle": "Joe Rogan",
        "actorAuthorTone": "His curiosity and conversational style",
        "spiritualPractices": "Meditation, nature walks, reading",
        "spiritualReflection": "Help me stay grounded and remind me of what matters",
        "lifeLandscape": "A vast desert with a clear path ahead",
        "safePlace": "A quiet library with warm lighting",
        "strengthSymbol": "A lighthouse in a storm",
        "sensoryAnchor": "Rain sounds, deep indigo, soft wool blankets",
        "chapterTitle": "Building the Future",
        "strengthMoment": "I finished a big project at work",
        "primaryHope": "To create something meaningful that helps others",
        "copingPattern": "I go for a run or work on a personal project",
    }

    print("=" * 80)
    print("PERSONA AGENT — FULL DEMONSTRATION")
    print("=" * 80)

    # Step 1: Extract personas
    personas = _extract_personas(onboarding_data)
    print(f"\n[STEP 1] Personas extracted:")
    print(f"  -> From 'inspirationFigure' (Elon Musk): {personas[0]}")
    print(f"  -> From 'actorAuthorStyle' (Joe Rogan): {personas[1]}")

    # Step 2: Build user context
    context = _build_user_context(onboarding_data)
    print(f"\n[STEP 2] User context from onboarding ({len(context)} chars):")
    print(f"{context}")

    # Step 3: Fetch DB profiles
    profiles = await get_multiple_celebrity_profiles(personas)
    print(f"\n[STEP 3] DB profiles found: {len(profiles)}")
    for p in profiles:
        print(f"  -> {p['name']}: {p['personality_traits'][:60]}...")
        print(f"     Speaking style: {p['speaking_style'][:60]}...")

    # Step 4: Mock tweets (real tweets would come from Twitter API)
    mock_tweets = [
        {"persona": "Elon Musk", "text": "When something is important enough, you do it even if the odds are not in your favor."},
        {"persona": "Elon Musk", "text": "I think it is possible for ordinary people to choose to be extraordinary."},
        {"persona": "Joe Rogan", "text": "The universe is a crazy place. We're all just figuring it out as we go."},
    ]

    # Step 5: Build the complete system prompt
    prompt = _build_system_prompt(personas, profiles, mock_tweets, context)

    print("\n" + "=" * 80)
    print("[STEP 5] COMPLETE SYSTEM PROMPT SENT TO LLM")
    print("=" * 80)
    print(prompt)
    print("=" * 80)

    # Step 6: Show what the AI message history looks like
    print("\n[STEP 6] EXAMPLE CHAT MESSAGE HISTORY:")
    print("-" * 80)
    print("SYSTEM (above prompt)")
    print("-" * 80)
    print("USER: I'm feeling a bit lost today. I don't know if I'm on the right path.")
    print("-" * 80)

    print("\n[EXPECTED AI RESPONSE]")
    print('  The AI would respond IN-CHARACTER as a blend of Elon Musk')
    print('  and Joe Rogan, using their speaking style, personality,')
    print('  and the user context to personalize the response.')
    print('  Example:')
    print()
    print('  "Man, I know that feeling. It\'s like standing on a launchpad')
    print('  watching the countdown clock — there\'s always that moment')
    print('  of doubt. But here\'s the thing: when something is important')
    print('  enough, you do it even if the odds aren\'t in your favor.')
    print('  You said your life feels like a desert with a clear path')
    print('  ahead — that sounds like you already know the direction.')
    print('  The question is, are you building the rocket, or just')
    print('  waiting for it to launch? What\'s one small step you')
    print('  could take today?"')

    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("1. The AI roleplays as BOTH Elon Musk and Joe Rogan")
    print("2. It uses their PERSONALITY + SPEAKING STYLE from stored profiles")
    print("3. It blends in TWEETS for current/recent context")
    print("4. It uses the USER'S OWN ANSWERS (14 questions) to personalize")
    print("5. The RELATIONAL FRAMEWORK ensures caring, trustworthy responses")
    print("6. Without DB profiles AND without tweets, it only has the name")
    print("=" * 80)


async def demo_unknown_person():
    print("\n\n")
    print("=" * 80)
    print("BONUS: Unknown Person (not in celebrity DB)")
    print("=" * 80)

    onboarding_data = {
        "inspirationFigure": "My Grandfather Ahmed",
        "inspirationQuality": "His wisdom, patience, and kindness to everyone",
        "spiritualPractices": "Prayer, family, helping neighbors",
        "primaryHope": "To be as kind and wise as he was",
    }

    personas = _extract_personas(onboarding_data)
    print(f"\nPersona: {personas[0]}")
    print(f"DB has him? No — no profile found")

    profiles = await get_multiple_celebrity_profiles(personas)
    print(f"Profiles fetched: {len(profiles)} (empty as expected)")

    context = _build_user_context(onboarding_data)
    print(f"\nUser context (what the AI knows about the user):")
    print(context)

    # No tweets either
    prompt = _build_system_prompt(personas, profiles, [], context)

    print(f"\nSystem prompt ({len(prompt)} chars, truncated):")
    # Show first 1000 chars
    print(prompt[:1000])
    print("...")

    print("\n[RESULT]")
    print('  The AI will roleplay as "My Grandfather Ahmed" using ONLY')
    print('  the name and the user\'s description. No stored personality')
    print('  data, no tweets. The LLM infers from the name + context.')
    print('  The more the user described them in their answers, the')
    print('  better the roleplay will be.')


async def main():
    await demo_persona()
    await demo_unknown_person()


if __name__ == "__main__":
    asyncio.run(main())
