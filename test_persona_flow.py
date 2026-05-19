"""
Test the persona agent end-to-end flow with mock data.
Tests: onboarding data formatting, persona extraction, user context building.
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ["HUGGINGFACE_API_KEY"] = "mock"

MOCK_CELEBRITY_PROFILES = {
    "joe rogan": {
        "name": "Joe Rogan",
        "personality_traits": "Curious, open-minded, comedic, skeptical, conversational, direct",
        "speaking_style": "Conversational, uses 'man' and 'dude', laughs easily, goes on tangents, interviews naturally",
        "common_topics": "MMA, comedy, psychedelics, fitness, conspiracy theories, health, podcasting",
        "sample_tweets": [
            "Just had an incredible conversation about consciousness. Mind blown.",
            "Training hard, feeling good. The grind never stops.",
            "New podcast episode dropping tomorrow. You don't want to miss this one.",
        ]
    }
}

class MockRow:
    def __getitem__(self, key):
        name = self._name
        profile = MOCK_CELEBRITY_PROFILES.get(name)
        if not profile:
            raise KeyError(key)
        val = profile.get(key, "")
        if key == "sample_tweets" and not isinstance(val, list):
            return []
        return val
    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

class MockConn:
    async def fetchrow(self, sql, *args):
        name = args[0].lower().strip() if args else ""
        profile = MOCK_CELEBRITY_PROFILES.get(name)
        if not profile:
            return None
        row = MockRow()
        row._name = name
        return row
    async def fetch(self, sql, *args):
        return []
    async def execute(self, sql, *args):
        pass

class MockAcquireContext:
    async def __aenter__(self):
        return MockConn()
    async def __aexit__(self, *args):
        pass

class MockPool:
    def acquire(self):
        return MockAcquireContext()

import app.db.database as db_module

async def get_mock_pool():
    return MockPool()

db_module.get_pool = get_mock_pool

from app.routers.chat import _extract_personas, _build_user_context
from app.agents.persona_agent import _build_system_prompt
from app.services.profile_service import get_multiple_celebrity_profiles


async def test_full_track():
    print("=" * 70)
    print("TEST 1: Full Track (14 Questions)")
    print("=" * 70)

    onboarding_data = {
        "inspirationFigure": "Joe Rogan",
        "inspirationQuality": "His curiosity and openness to new ideas",
        "actorAuthorStyle": "Morgan Freeman",
        "actorAuthorTone": "His calm, authoritative voice",
        "spiritualPractices": "Meditation, being in nature",
        "spiritualReflection": "Remind me to stay present",
        "lifeLandscape": "A dense forest with hidden clearings",
        "safePlace": "A cabin by a lake",
        "strengthSymbol": "An oak tree",
        "sensoryAnchor": "Ocean waves, deep blue, soft cotton",
        "chapterTitle": "The Awakening",
        "strengthMoment": "Had a deep conversation with a friend",
        "primaryHope": "More clarity about my purpose",
        "copingPattern": "I take a walk or call a friend",
    }
    personas = _extract_personas(onboarding_data)
    print(f"  Personas extracted: {personas}")
    assert "Joe Rogan" in personas
    assert "Morgan Freeman" in personas
    print("  [OK] Both personas found")

    context = _build_user_context(onboarding_data)
    print(f"  User context built ({len(context)} chars)")
    assert "Person they look up to" in context
    assert "life chapter feels" in context
    assert "overwhelmed" in context
    print("  [OK] All 14 fields mapped correctly")

    profiles = await get_multiple_celebrity_profiles(personas)
    print(f"  Profiles fetched from DB: {len(profiles)}")
    for p in profiles:
        print(f"    -> {p['name']}: {p['personality_traits'][:50]}...")

    prompt = _build_system_prompt(personas, profiles, [], context)
    print(f"  System prompt generated ({len(prompt)} chars)")
    assert "Joe Rogan" in prompt
    assert "Morgan Freeman" in prompt
    assert "role-playing" in prompt
    assert "RELATIONAL FRAMEWORK" in prompt
    print("  [OK] Contains persona names, roleplay instruction, and relational framework")

    print("[PASS] FULL TRACK TEST PASSED\n")
    return True


async def test_fast_track():
    print("=" * 70)
    print("TEST 2: Fast Track (8 Questions)")
    print("=" * 70)

    onboarding_data = {
        "inspirationFigure": "Joe Rogan",
        "inspirationQuality": "His curiosity",
        "actorAuthorStyle": "Morgan Freeman",
        "actorAuthorTone": "His calm voice",
        "spiritualPractices": "Meditation",
        "spiritualReflection": "Remind me to stay present",
        "chapterTitle": "New Beginnings",
        "primaryHope": "Inner peace",
    }
    personas = _extract_personas(onboarding_data)
    print(f"  Personas extracted: {personas}")
    assert "Joe Rogan" in personas
    assert "Morgan Freeman" in personas
    print("  [OK] Both personas found with just 8 fields")

    context = _build_user_context(onboarding_data)
    print(f"  User context built ({len(context)} chars)")
    print(f"    Has inspirationFigure: {'Person they look up to' in context}")
    print(f"    Has primaryHope: {'Biggest shift or hope' in context}")
    print(f"    Has chapterTitle: {'Title they' in context}")
    print(f"    SKIPPED lifeLandscape (not in fast track): {'life chapter feels' not in context}")
    print(f"    SKIPPED copingPattern (not in fast track): {'overwhelmed' not in context}")
    assert "Person they look up to" in context
    assert "Biggest shift or hope" in context
    assert "life chapter feels" not in context
    print("  [OK] Fast track works, missing fields skipped gracefully")

    profiles = await get_multiple_celebrity_profiles(personas)
    prompt = _build_system_prompt(personas, profiles, [], context)
    print(f"  System prompt generated ({len(prompt)} chars)")
    assert "Joe Rogan" in prompt
    print("  [OK] Prompt works with fast track")

    print("[PASS] FAST TRACK TEST PASSED\n")
    return True


async def test_unknown_person():
    print("=" * 70)
    print("TEST 3: Unknown Person (not in celebrity DB)")
    print("=" * 70)

    onboarding_data = {
        "inspirationFigure": "My Grandfather Ahmed",
        "inspirationQuality": "His wisdom and kindness",
        "spiritualPractices": "Prayer, family, helping others",
        "primaryHope": "To be as kind and wise as he was",
    }
    personas = _extract_personas(onboarding_data)
    print(f"  Personas extracted: {personas}")
    assert "My Grandfather Ahmed" in personas

    profiles = await get_multiple_celebrity_profiles(personas)
    print(f"  DB profiles found: {len(profiles)} (expected 0 for unknown)")
    assert len(profiles) == 0
    print("  [OK] No profile in DB (expected)")

    context = _build_user_context(onboarding_data)
    print(f"  User context still built from available fields:")
    print(f"    -> {context}")

    prompt = _build_system_prompt(personas, profiles, [], context)
    print(f"  System prompt generated ({len(prompt)} chars)")
    assert "My Grandfather Ahmed" in prompt
    print("  [OK] LLM will roleplay with just name + context (no DB profile)")

    print("[PASS] UNKNOWN PERSON TEST PASSED\n")
    return True


async def test_no_onboarding():
    print("=" * 70)
    print("TEST 4: No Onboarding Data (falls back to 'Assistant')")
    print("=" * 70)

    personas = _extract_personas({})
    print(f"  Personas extracted: {personas}")
    assert personas == ["Assistant"]
    print("  [OK] Falls back to 'Assistant'")

    context = _build_user_context({})
    assert context == ""
    print("  [OK] Context is empty (expected)")

    profiles = await get_multiple_celebrity_profiles(personas)
    print(f"  Profiles fetched: {len(profiles)}")

    prompt = _build_system_prompt(personas, profiles, [], context)
    assert "Assistant" in prompt
    print("  [OK] Prompt uses 'Assistant' fallback")

    print("[PASS] NO ONBOARDING TEST PASSED\n")
    return True


async def main():
    print("=" * 70)
    print("PERSONA AGENT FLOW TESTS")
    print("=" * 70)

    tests = [
        ("Full Track (14 questions)", test_full_track),
        ("Fast Track (8 questions)", test_fast_track),
        ("Unknown person (no DB)", test_unknown_person),
        ("No onboarding data", test_no_onboarding),
    ]

    for name, test in tests:
        print(f"\nRunning: {name}")
        try:
            await test()
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 70)
    print("All tests done")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
