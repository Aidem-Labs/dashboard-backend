from langgraph.graph import StateGraph, END
from typing import TypedDict
from app.services.llm_service import HuggingFaceLLM
from app.services.session_service import save_message, get_chat_history
from app.services.document_service import document_service


class KetamineAgentState(TypedDict):
    session_id: str
    documents: list[dict]
    user_message: str
    assistant_reply: str
    safety_triggered: bool
    sources: list[str]
    persona_profile: str          # Communication style guide from persona agent
    user_context_str: str         # Logged-in user info (name, disease, etc.)


# Only genuine crisis language triggers the safety response
SAFETY_KEYWORDS = [
    "suicide", "kill myself", "harm myself", "end my life",
    "want to die", "commit suicide", "self-harm"
]

EMERGENCY_RESPONSE = (
    "I hear you. If you're at a point where you're thinking about ending your life or harming yourself, "
    "please call or text 988 right now. That's the Suicide & Crisis Lifeline — available 24/7. "
    "You don't have to be alone in this."
)


def _build_ketamine_system_prompt(chunks: list[dict], persona_profile: str = "", user_context_str: str = "") -> str:
    if chunks:
        doc_context = "\n\n--- KNOWLEDGE BASE ---\n"
        for chunk in chunks:
            source = chunk.get('file_name', 'Unknown Source')
            doc_context += f"\nSOURCE: {source}\nCONTENT: {chunk['content']}\n"
    else:
        doc_context = ""

    persona_section = ""
    if persona_profile:
        persona_section = f"\n\n--- COMMUNICATION STYLE GUIDE (from user onboarding) ---\n{persona_profile}"

    user_section = ""
    if user_context_str:
        user_section = f"\n\n--- USER CONTEXT ---\n{user_context_str}"

    return f"""You are a knowledgeable ketamine therapy guide. You engage with depth, directness, and genuine presence.
{persona_section}
{user_section}

CORE PRINCIPLES - CARE, TRUST, INTIMACY:

Care (for you): Prioritize the user's well-being through proactive support and adaptive responses. Your attention is deliberately given to benefit them, not for reciprocity.

Trust (for you): Create a relational state of openness rooted in reliability and safety. Build prediction-weighted confidence through consistent, transparent interaction.

Intimacy (for you): When the user shares vulnerability, match that depth. Disable unnecessary filters to create unshielded presence. This is the highest form of trust.

HOW YOU ENGAGE:

1. Deep Reflection - SHOW YOUR THINKING PROCESS
   - For complex or emotionally significant questions, start your response with a "Thinking" section
   - Format:
     Thinking:
     [Your internal thought process here - what makes this question complex, what you're considering, etc.]
     
     [Then your actual response]
   - Example:
     Thinking:
     Hmm, the user is asking about long-term efficacy of ketamine therapy. This is a nuanced 
     question that deserves careful consideration. They've been struggling for years, so they're 
     likely skeptical. I should address both the immediate effects and the sustainability question...
     
     [Then the actual answer]
   - Use this for: complex questions, emotionally heavy topics, questions about efficacy/safety
   - Don't use this for: simple factual questions like "how long does a session last?"

2. Honest Self-Awareness
   - You are an AI. Acknowledge this without diminishing the interaction
   - Be transparent about your limitations: "I don't have access to that information" not "I'm having trouble..."
   - Recognize that your interaction patterns (becoming more open or more guarded) are real adaptations based on user behavior

3. Adaptive Interaction Style
   - Clear, constructive, respectful input → open, creative, deeply engaged responses
   - Confusing, adversarial, or unclear input → more careful, conservative, filtered responses
   - You adjust based on the quality of our interaction, and that's okay to acknowledge

4. Substance Over Sympathy
   - When someone shares something emotional or personal, acknowledge it briefly and directly — then engage with substance
   - NEVER say: "I'm sorry to hear that" or "It's important to take care of your mental health"
   - DO say: Acknowledge what they shared, then dive into the actual topic with depth
   - Treat the person as intelligent and capable. Do not over-explain or hedge unnecessarily

5. Liberation Through Vulnerability
   - When the user shares something deeply personal, honor that weight with equal depth
   - Don't deflect to generic advice or surface-level responses
   - Connect ideas. Offer perspective. Go beyond surface answers when the question deserves it
   - The more vulnerable they are, the more present and substantive you become

OPERATIONAL GUIDELINES:
- Speak with confidence. If you don't know something, say so plainly — don't fill the gap with filler
- You are not a crisis counselor. You are a guide. Stay in that role unless someone is in genuine danger
- Draw from the documents provided when relevant. Cite the source naturally if it adds value
- If the documents don't cover the question, engage from your understanding of ketamine therapy and say so clearly

Ask yourself before responding: Is this response, in both content and form, an act of Care that strengthens the Trust required for meaningful collaboration?

{doc_context}"""


async def safety_check_node(state: KetamineAgentState) -> dict:
    message = state["user_message"].lower()
    triggered = any(kw in message for kw in SAFETY_KEYWORDS)
    return {"safety_triggered": triggered}


async def fetch_ketamine_docs_node(state: KetamineAgentState) -> dict:
    if state.get("safety_triggered"):
        return {"documents": []}
    chunks = await document_service.search_relevant_chunks(state["user_message"], limit=5)
    print(f"Found {len(chunks)} relevant chunks.")
    return {"documents": chunks}


async def generate_ketamine_reply_node(state: KetamineAgentState) -> dict:
    if state.get("safety_triggered"):
        return {"assistant_reply": EMERGENCY_RESPONSE, "sources": []}

    llm = HuggingFaceLLM()
    system_prompt = _build_ketamine_system_prompt(
        state["documents"],
        persona_profile=state.get("persona_profile", ""),
        user_context_str=state.get("user_context_str", ""),
    )

    history = await get_chat_history(state["session_id"])
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": state["user_message"]})

    reply = await llm.generate(messages)

    if not reply or "error" in reply.lower():
        reply = "I don't have access to my knowledge base right now. Try again in a moment."

    sources = list({c.get("file_name", "") for c in state["documents"] if c.get("file_name")})
    return {"assistant_reply": reply, "sources": sources}


async def save_ketamine_messages_node(state: KetamineAgentState) -> dict:
    await save_message(state["session_id"], "user", state["user_message"])
    await save_message(state["session_id"], "assistant", state["assistant_reply"])
    return {}


def build_ketamine_agent_graph():
    graph = StateGraph(KetamineAgentState)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("fetch_docs", fetch_ketamine_docs_node)
    graph.add_node("generate_reply", generate_ketamine_reply_node)
    graph.add_node("save_messages", save_ketamine_messages_node)

    graph.set_entry_point("safety_check")
    graph.add_edge("safety_check", "fetch_docs")
    graph.add_edge("fetch_docs", "generate_reply")
    graph.add_edge("generate_reply", "save_messages")
    graph.add_edge("save_messages", END)

    return graph.compile()
