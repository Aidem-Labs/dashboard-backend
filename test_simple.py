"""Simple test: hit the local backend /api/chat"""
import httpx, asyncio, json, uuid

async def test():
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": "Hey! I'm feeling anxious about building something meaningful. What advice would you give?",
        "onboarding_data": {
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
    }
    async with httpx.AsyncClient(timeout=180) as client:
        print("Sending to http://localhost:8000/api/chat ...")
        r = await client.post("http://localhost:8000/api/chat", json=payload)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"\nSession: {data['session_id']}")
            print(f"Personas: {data['personas']}")
            print(f"\n--- AI RESPONSE ({len(data['response'])} chars) ---")
            safe = data['response'].encode('ascii', 'replace').decode('ascii')
            print(safe[:500])
            print("--- END ---")
        else:
            print(f"Error body: {r.text[:500]}")

asyncio.run(test())
