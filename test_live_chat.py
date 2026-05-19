"""
Live test: sends a chat message to the persona agent.
The backend server must already be running on port 8000.
"""
import httpx
import asyncio
import json
import uuid
import sys

SESSION_ID = str(uuid.uuid4())

FULL_TRACK_14 = {
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

FAST_TRACK_8 = {
    "inspirationFigure": "Elon Musk",
    "inspirationQuality": "His vision and determination",
    "actorAuthorStyle": "Joe Rogan",
    "actorAuthorTone": "His curiosity",
    "spiritualPractices": "Meditation",
    "spiritualReflection": "Stay grounded",
    "chapterTitle": "Building the Future",
    "primaryHope": "To create something meaningful",
}


async def test_full_track():
    print("=" * 70)
    print("TEST 1: Full Track (14 questions) -> Elon Musk + Joe Rogan")
    print("=" * 70)

    payload = {
        "session_id": SESSION_ID,
        "message": "Hey man, I've been feeling really anxious lately. Like there's this pressure to build something great but I don't know where to start. What would you do?",
        "onboarding_data": FULL_TRACK_14,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("http://localhost:8000/api/chat", json=payload)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text}")
            return False

        data = r.json()
        print(f"\nSession ID: {data['session_id']}")
        print(f"Personas used: {data['personas']}")
        print(f"\n--- AI RESPONSE ---")
        print(data['response'])
        print("--- END ---\n")

        # Verify the response is in-character
        response_lower = data['response'].lower()
        elon_signals = ['mars', 'tesla', 'spacex', 'rocket', 'future', 'build']
        joe_signals = ['man', 'dude', 'conversation', 'podcast', 'crazy']

        elon_hits = sum(1 for s in elon_signals if s in response_lower)
        joe_hits = sum(1 for s in joe_signals if s in response_lower)
        print(f"Elon-style signals: {elon_hits}/6")
        print(f"Joe-style signals: {joe_hits}/5")
        print(f"Total persona flavor: {elon_hits + joe_hits}/11")

        if elon_hits + joe_hits >= 2:
            print("[PASS] AI responded in-character as Elon + Joe")
        else:
            print("[NOTE] Light persona flavor - LLM may generalize without tweets")

    return True


async def test_unknown_person():
    print("=" * 70)
    print("TEST 2: Unknown Person (not in celebrity DB)")
    print("=" * 70)

    session2 = str(uuid.uuid4())
    payload = {
        "session_id": session2,
        "message": "I'm feeling lost today. What advice would you give me?",
        "onboarding_data": {
            "inspirationFigure": "My Grandfather Ahmed",
            "inspirationQuality": "His wisdom, patience, and kindness to everyone",
            "spiritualPractices": "Prayer, family, helping neighbors",
            "primaryHope": "To be as kind and wise as he was",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("http://localhost:8000/api/chat", json=payload)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text}")
            return False

        data = r.json()
        print(f"\nPersonas used: {data['personas']}")
        print(f"\n--- AI RESPONSE ---")
        print(data['response'])
        print("--- END ---\n")
        print("[NOTE] No DB profile for 'My Grandfather Ahmed'")
        print("      AI roleplays using only the name + user's description")

    return True


async def test_no_onboarding():
    print("=" * 70)
    print("TEST 3: No onboarding data -> Falls back to 'Assistant'")
    print("=" * 70)

    session3 = str(uuid.uuid4())
    payload = {
        "session_id": session3,
        "message": "Hello, can you help me today?",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("http://localhost:8000/api/chat", json=payload)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text}")
            return False

        data = r.json()
        print(f"\nPersonas used: {data['personas']}")
        print(f"\n--- AI RESPONSE ---")
        print(data['response'])
        print("--- END ---\n")
        assert data['personas'] == ['Assistant']
        print("[PASS] Falls back to 'Assistant' persona")

    return True


async def main():
    print("Backend chat test - checking server...")
    async with httpx.AsyncClient(timeout=5) as c:
        try:
            r = await c.get("http://localhost:8000/health")
            print(f"Server: {r.json()['message']}\n")
        except Exception as e:
            print(f"ERROR: Backend not running on port 8000 - {e}")
            print("Start it with: python main.py")
            return

    tests = [
        ("Full Track (14 questions)", test_full_track),
        ("Unknown Person", test_unknown_person),
        ("No Onboarding", test_no_onboarding),
    ]

    for name, test in tests:
        try:
            await test()
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
        print()


if __name__ == "__main__":
    asyncio.run(main())
