from langgraph.graph import StateGraph, END
from typing import TypedDict
from app.services.llm_service import HuggingFaceLLM
from app.services.session_service import save_message, get_chat_history
from app.services.tweet_service import fetch_celebrity_tweets
from app.services.profile_service import get_multiple_celebrity_profiles
from app.utils.relational_framework import get_relational_system_prompt



class AgentState(TypedDict):
    session_id: str
    personas: list[str]
    stored_profiles: list[dict]
    tweets: list[dict]
    user_message: str
    assistant_reply: str
    user_context: str


def _build_system_prompt(personas: list[str], profiles: list[dict], tweets: list[dict], user_context: str = "") -> str:
    """Build system prompt combining stored personality + fresh tweets + user context."""
    persona_names = " and ".join(personas) if len(personas) <= 2 else ", ".join(personas[:-1]) + f", and {personas[-1]}"

    # Build personality context from stored data
    personality_context = ""
    for profile in profiles:
        personality_context += f"\n\n--- {profile['name'].upper()} ---\n"
        personality_context += f"Personality: {profile['personality_traits']}\n"
        personality_context += f"Speaking Style: {profile['speaking_style']}\n"
        personality_context += f"Common Topics: {profile['common_topics']}\n"
        personality_context += f"Example things they've said:\n"
        sample = profile.get('sample_tweets', [])
        for i, tweet in enumerate(sample[:4]):
            personality_context += f"  - \"{tweet}\"\n"

    # Build fresh tweet context
    tweet_context = ""
    if tweets:
        tweet_context = "\n\nRECENT TWEETS (fresh data):\n"
        tweet_context += "\n".join([
            f"[{t.get('persona', 'unknown')}] \"{t['text']}\""
            for t in tweets
        ])

    prompt = f"""You are now role-playing as {persona_names}.

{personality_context}
{tweet_context}

IMPORTANT RULES:
- Stay completely in character as {persona_names}
- Use their stored personality traits AND speaking style above
- If fresh tweets are provided, blend them with the stored personality for current responses
- If no fresh tweets, rely fully on the stored personality data
- If multiple personas, blend their personalities naturally
- Speak, think, and respond exactly like they would
- Use their tone, style, slang, and opinions
- Never break character or mention that you are an AI
- Keep responses natural and conversational

Respond to the user as {persona_names} would."""

    prompt += "\n" + get_relational_system_prompt()

    if user_context:
        prompt += f"\n\n{user_context}"

    return prompt


async def fetch_profiles_node(state: AgentState) -> dict:
    """Get pre-stored personality data from DB (cheap, always available)."""
    print("\n" + "="*80)
    print("👥 AGENT NODE 1: FETCHING CELEBRITY PROFILES")
    print("="*80)
    print(f"📋 Personas: {', '.join(state['personas'])}")
    print("⏳ Fetching personality profiles from database...")
    
    profiles = await get_multiple_celebrity_profiles(state["personas"])
    
    print(f"✅ Successfully fetched {len(profiles)} profiles")
    for profile in profiles:
        print(f"   → {profile['name']}: {profile['personality_traits'][:50]}...")
    print("="*80 + "\n")
    
    return {"stored_profiles": profiles}


async def fetch_tweets_node(state: AgentState) -> dict:
    """Fetch fresh tweets from Twitter API (real-time data)."""
    print("\n" + "="*80)
    print("🐦 AGENT NODE 2: FETCHING FRESH TWEETS")
    print("="*80)
    print(f"📋 Fetching tweets for: {', '.join(state['personas'])}")
    print("⏳ Starting tweet scraping...")
    
    all_tweets = []
    for persona in state["personas"]:
        print(f"\n   → Fetching tweets for: {persona}")
        tweets = await fetch_celebrity_tweets(persona, count=10)
        for t in tweets:
            t["persona"] = persona
        all_tweets.extend(tweets)
        print(f"   ✅ Got {len(tweets)} tweets for {persona}")
    
    print(f"\n✅ Total tweets collected: {len(all_tweets)}")
    print("="*80 + "\n")
    
    return {"tweets": all_tweets}


async def generate_reply_node(state: AgentState) -> dict:
    """Generate response using BOTH stored personality + fresh tweets + user context."""
    print("\n" + "="*80)
    print("💬 AGENT NODE 3: GENERATING AI RESPONSE")
    print("="*80)
    print(f"👤 Personas: {', '.join(state['personas'])}")
    print(f"📊 Profiles loaded: {len(state['stored_profiles'])}")
    print(f"🐦 Tweets loaded: {len(state['tweets'])}")
    print(f"💭 User message: {state['user_message']}")
    print("⏳ Building system prompt and calling AI...")
    
    llm = HuggingFaceLLM()

    system_prompt = _build_system_prompt(
        state["personas"],
        state["stored_profiles"],
        state["tweets"],
        state.get("user_context", ""),
    )

    # Get chat history
    history = await get_chat_history(state["session_id"])
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": state["user_message"]})

    print("\n⏳ Calling HuggingFace AI model...")
    reply = await llm.generate(messages)
    
    print(f"\n✅ AI Response generated! ({len(reply)} characters)")
    print("="*80 + "\n")
    
    return {"assistant_reply": reply}


async def save_messages_node(state: AgentState) -> dict:
    """Save user message and assistant reply to database."""
    print("\n" + "="*80)
    print("💾 AGENT NODE 4: SAVING MESSAGES TO DATABASE")
    print("="*80)
    print(f"📝 Session ID: {state['session_id']}")
    print(f"💬 User message: {state['user_message'][:50]}...")
    print(f"🤖 Assistant reply: {state['assistant_reply'][:50]}...")
    print("⏳ Saving to database...")
    
    await save_message(state["session_id"], "user", state["user_message"])
    await save_message(state["session_id"], "assistant", state["assistant_reply"])
    
    print("✅ Messages saved successfully!")
    print("="*80 + "\n")
    
    return {}


def build_agent_graph():
    """Build LangGraph agent with 4 nodes:
    1. Fetch stored personality profiles (cheap, always works)
    2. Fetch fresh tweets (real-time, may cost money)
    3. Generate reply (combines both sources)
    4. Save messages to DB
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("fetch_profiles", fetch_profiles_node)
    graph.add_node("fetch_tweets", fetch_tweets_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.add_node("save_messages", save_messages_node)

    # Set entry point
    graph.set_entry_point("fetch_profiles")

    # Profile and tweet fetching happen in sequence (can be parallel later)
    graph.add_edge("fetch_profiles", "fetch_tweets")

    # Both sources combined → generate reply
    graph.add_edge("fetch_tweets", "generate_reply")
    graph.add_edge("generate_reply", "save_messages")
    graph.add_edge("save_messages", END)

    return graph.compile()
