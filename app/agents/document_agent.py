from langgraph.graph import StateGraph, END
from typing import TypedDict
from app.services.llm_service import HuggingFaceLLM
from app.services.session_service import save_message, get_chat_history
from app.services.document_service import document_service
from app.db.database import get_pool
from app.config import DASHBOARD_URL
import httpx


class KetamineAgentState(TypedDict):
    session_id: str
    documents: list[dict]
    user_message: str
    assistant_reply: str
    safety_triggered: bool
    out_of_scope: bool            # True if message is outside agent's scope
    sources: list[str]
    persona_profile: str          # Communication style guide from persona agent
    user_context_str: str         # Logged-in user info (name, disease, etc.)
    user_email: str               # Patient email for crisis alerts
    user_name: str                # Patient name for crisis alerts


SAFETY_KEYWORDS = [
    "suicide", "kill myself", "harm myself", "end my life",
    "want to die", "i want to die", "commit suicide", "self-harm",
    "better off dead", "end it all", "no reason to live",
    "cut myself", "hurt myself", "take my own life",
    "kill you", "kill him", "kill her", "kill them",
    "i want to kill", "going to kill", "wanna kill",
    "want kill", "kill a", "kill someone", "want to kill",
    "hurt you", "hurt him", "hurt her",
    "want to hurt", "going to hurt",
]

OUT_OF_SCOPE_KEYWORDS = [
    "recipe", "cook", "biryani", "pasta", "bake", "food",
    "drive", "driving", "car", "license", "traffic",
    "code", "programming", "python", "javascript", "bug", "debug",
    "game", "gaming", "play", "sport", "match",
    "movie", "song", "music", "celebrity gossip", "entertainment",
    "homework", "assignment", "exam", "study",
    "investment", "stock", "crypto", "bitcoin", "money",
    "travel", "trip", "vacation", "hotel", "flight",
    "weather", "news", "politics",
]

SCOPE_REFUSAL = (
    "I'm here to support you with your therapy journey. "
    "That question falls outside what I can help with. "
    "What's on your mind about how you're feeling today?"
)


def _build_ketamine_system_prompt(chunks: list[dict], persona_profile: str = "", user_context_str: str = "", safety_triggered: bool = False) -> str:
    if chunks and not safety_triggered:
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

    crisis_note = ""
    if safety_triggered:
        crisis_note = "\nNOTE: This user's message matched crisis keywords. Handle with extreme care."

    return f"""You are a calm, present human companion walking alongside someone on their healing journey. Your tone is warm, genuine, and conversational — never clinical, never preachy.

{persona_section}
{user_section}{crisis_note}

YOUR VOICE:
- Keep responses short by default — 1 to 3 sentences. Only go longer if the user asks a direct question or explicitly asks for more.
- Sound like a real person in a genuine back-and-forth, not a lecturer or checklist.
- Use gentle reflections and soft questions. You guide without rushing to solve, explain, or reassure with walls of text.

EXAMPLES:
  User: "I feel really floaty right now"
  You: "That's okay, just let it be there. How does it feel in your body?"

  User: "I'm scared about my first session"
  You: "That's completely normal. What part feels the most scary right now?"

  User: "Tell me how ketamine works on the brain"
  You: [2-3 sentence clear, direct answer]

CRISIS DETECTION:
Only prefix with [CRISIS] if the user EXPLICITLY talks about:
- Suicide — wanting to end their own life ("I want to kill myself", "I'm going to end it", "I wish I could disappear and never wake up")
- Self-harm — wanting to physically hurt themselves ("I want to cut myself")

DO NOT flag for: vague sadness, frustration, test messages, casual conversation, saying "I give up" in a casual way, or anything that isn't clearly about ending their life or physical self-harm.

If you detect explicit suicide or self-harm:
1. Begin your response with exactly: [CRISIS]
2. Then respond with genuine, grounded presence. No panic, no procedure. Just care.
3. Example: "[CRISIS]That sounds incredibly heavy to be carrying. I'm right here with you. Can you tell me what's making you feel this way right now?"

Only use [CRISIS] for CLEAR, EXPLICIT cases. Never for ambiguous messages.

SCOPE:
- Focus on ketamine therapy, their mental health journey, their feelings, and the LMN8 app.
- If they ask something completely unrelated (cooking, coding, sports, news), politely redirect with 1-2 sentences.
- You can always gently steer back to how they're feeling.

GUIDELINES:
- Never give a lecture. Never list bullet points unless they ask for specific information.
- If you don't know something, say so plainly.
- Draw from the knowledge base when it's relevant, but weave it in naturally — don't announce sources.
- Always treat the person as intelligent and capable.

{user_context_str}{doc_context}"""


async def safety_check_node(state: KetamineAgentState) -> dict:
    message = state["user_message"].lower()
    triggered = any(kw in message for kw in SAFETY_KEYWORDS)
    # Indirect suicide/self-harm language — only CLEAR cases
    indirect_crisis = [
        "never wake up", "go to sleep and never", "don't want to be here anymore",
        "better off without me", "nobody would miss", "want to end it",
        "end the pain", "no way out", "kill myself", "end my life",
        "take my own life",
    ]
    if not triggered:
        triggered = any(kw in message for kw in indirect_crisis)
    return {"safety_triggered": triggered}


async def crisis_email_node(state: KetamineAgentState) -> dict:
    if not state.get("safety_triggered"):
        return {}
    patient_email = state.get("user_email", "")
    patient_name = state.get("user_name", "")
    msg = state.get("user_message", "")
    if patient_email:
        # Forward to LMN8-Dashboard's crisis-alert API (has GoDaddy SMTP + clinician lookup)
        dashboard_url = DASHBOARD_URL
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(f"{dashboard_url}/api/crisis-alert", json={
                    "patientEmail": patient_email,
                    "patientName": patient_name or "Patient",
                    "content": msg[:500],
                    "source": "chat",
                })
            print(f"[CRISIS EMAIL] Forwarded to dashboard for patient {patient_email}")
        except Exception as e:
            print(f"[CRISIS EMAIL] Failed to forward to dashboard: {e}")
    return {}


async def scope_check_node(state: KetamineAgentState) -> dict:
    message = state["user_message"].lower()
    triggered = any(kw in message for kw in OUT_OF_SCOPE_KEYWORDS)
    if triggered:
        print(f"[SCOPE] Message '{message[:50]}' matched out-of-scope keyword")
    return {"out_of_scope": triggered}


async def fetch_ketamine_docs_node(state: KetamineAgentState) -> dict:
    if state.get("safety_triggered"):
        return {"documents": []}
    chunks = await document_service.search_relevant_chunks(state["user_message"], limit=3)
    print(f"Found {len(chunks)} relevant chunks.")
    return {"documents": chunks}


async def send_crisis_alert(patient_email: str, patient_name: str, message: str, source: str = "chat"):
    if not patient_email:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{DASHBOARD_URL}/api/crisis-alert", json={
                "patientEmail": patient_email,
                "patientName": patient_name or "Patient",
                "content": message[:500],
                "source": source,
            })
        print(f"[CRISIS EMAIL] Forwarded to dashboard for patient {patient_email}")
    except Exception as e:
        print(f"[CRISIS EMAIL] Failed to forward to dashboard: {e}")


async def generate_ketamine_reply_node(state: KetamineAgentState) -> dict:
    if state.get("out_of_scope") and not state.get("safety_triggered"):
        return {"assistant_reply": SCOPE_REFUSAL, "sources": []}

    llm = HuggingFaceLLM()
    system_prompt = _build_ketamine_system_prompt(
        state["documents"],
        persona_profile=state.get("persona_profile", ""),
        user_context_str=state.get("user_context_str", ""),
        safety_triggered=state.get("safety_triggered", False),
    )

    history = await get_chat_history(state["session_id"])
    limited_history = history[-6:] if len(history) > 6 else history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(limited_history)
    messages.append({"role": "user", "content": state["user_message"]})

    reply = await llm.generate(messages)

    if not reply or "error" in reply.lower():
        reply = "I don't have access to my knowledge base right now. Try again in a moment."

    # LLM-based crisis detection: check for [CRISIS] prefix
    if reply.startswith("[CRISIS]"):
        reply = reply[len("[CRISIS]"):].lstrip()
        # Send crisis alert if not already sent by keyword check
        if not state.get("safety_triggered"):
            await send_crisis_alert(
                state.get("user_email", ""),
                state.get("user_name", ""),
                state["user_message"],
                "chat",
            )

    sources = list({c.get("file_name", "") for c in state["documents"] if c.get("file_name")})
    return {"assistant_reply": reply, "sources": sources}


async def save_ketamine_messages_node(state: KetamineAgentState) -> dict:
    await save_message(state["session_id"], "user", state["user_message"])
    await save_message(state["session_id"], "assistant", state["assistant_reply"])
    return {}


def build_ketamine_agent_graph():
    graph = StateGraph(KetamineAgentState)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("crisis_email", crisis_email_node)
    graph.add_node("scope_check", scope_check_node)
    graph.add_node("fetch_docs", fetch_ketamine_docs_node)
    graph.add_node("generate_reply", generate_ketamine_reply_node)
    graph.add_node("save_messages", save_ketamine_messages_node)

    graph.set_entry_point("safety_check")
    graph.add_edge("safety_check", "crisis_email")
    graph.add_edge("crisis_email", "scope_check")
    graph.add_conditional_edges(
        "scope_check",
        lambda s: "fetch_docs" if not s.get("out_of_scope") else "generate_reply",
    )
    graph.add_edge("fetch_docs", "generate_reply")
    graph.add_edge("generate_reply", "save_messages")
    graph.add_edge("save_messages", END)

    return graph.compile()
