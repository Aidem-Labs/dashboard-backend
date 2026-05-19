"""Test: ask the agent 'What do you know about me?' to verify it knows onboarding data."""
import httpx, asyncio, json, uuid

onboarding_data = {
    "inspirationFigure": "Elon Musk",
    "inspirationQuality": "His vision and determination to change the world",
    "actorAuthorStyle": "Joe Rogan",
    "actorAuthorTone": "His curiosity and conversational style",
    "spiritualPractices": "Meditation, nature walks, reading",
    "spiritualReflection": "Help me stay grounded",
    "lifeLandscape": "A vast desert with a clear path ahead",
    "safePlace": "A quiet library with warm lighting",
    "strengthSymbol": "A lighthouse in a storm",
    "sensoryAnchor": "Rain sounds, deep indigo",
    "chapterTitle": "Building the Future",
    "strengthMoment": "I finished a big project at work",
    "primaryHope": "To create something meaningful that helps others",
    "copingPattern": "I go for a run or work on a personal project",
}

async def test():
    async with httpx.AsyncClient(timeout=180) as client:
        # 1. Show the user context the agent sees
        print("="*70)
        print("YOUR ONBOARDING ANSWERS SENT TO THE AGENT:")
        print("="*70)
        for k, v in onboarding_data.items():
            print(f"  {k}: {v}")

        print("\n\n")

        # 2. Map them to the user context format
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
        print("="*70)
        print("USER CONTEXT INJECTED INTO SYSTEM PROMPT:")
        print("="*70)
        for key, label in mapping.items():
            value = onboarding_data.get(key)
            if value:
                print(f"  - {label}: {value}")
        
        print("\n\n")

        # 3. Send the question
        payload = {
            "session_id": str(uuid.uuid4()),
            "message": "What do you know about me? Be specific about the details I shared with you during onboarding.",
            "onboarding_data": onboarding_data,
        }
        print("Sending: 'What do you know about me?'")
        print("="*70)
        r = await client.post("http://localhost:8000/api/chat", json=payload)
        data = r.json()
        print(f"\nStatus: {r.status_code}")
        if r.status_code == 200:
            print(f"Session: {data['session_id']}")
            print(f"Personas: {data['personas']}")
            print(f"\n--- AGENT'S FULL RESPONSE ---")
            safe = data['response'].encode('ascii', 'replace').decode('ascii')
            print(safe)
            print("--- END ---")
        else:
            print(f"Error: {data}")

asyncio.run(test())
