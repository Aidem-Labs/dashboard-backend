# METAT8 Backend

AI Persona Chat Agent - Responds like user's chosen celebrities using their tweets.

## Tech Stack

- **Backend**: Python + FastAPI
- **Agent Framework**: LangGraph
- **Database**: Neon DB (PostgreSQL)
- **LLM**: Hugging Face Inference API
- **Tweet Fetching**: TwitterAPI.io (or mock data for testing)

## Setup

1. **Create virtual environment** (already done):
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set up Neon DB**:
   - Go to [neon.tech](https://neon.tech)
   - Create a project and database
   - Copy the connection string
   - Paste it in `.env` as `DATABASE_URL`

3. **Set up Hugging Face**:
   - Get your API key from [huggingface.co](https://huggingface.co/settings/tokens)
   - Paste it in `.env` as `HUGGINGFACE_API_KEY`
   - Set model in `.env` (e.g., `meta-llama/Llama-3.1-70B-Instruct`)

4. **(Optional) Set up Twitter API**:
   - Get API key from [twitterapi.io](https://twitterapi.io)
   - Paste it in `.env` as `TWITTER_API_KEY`
   - If not set, the app uses mock tweets for testing

5. **Run the server**:
   ```bash
   .\venv\Scripts\activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### 1. Create Session (Welcome Screen)
```
POST /api/session
Body:
{
  "ideal_person": "Elon Musk",
  "favourite_celebrity": "Lionel Messi",
  "celebrity_to_talk": null
}
Response:
{
  "id": "uuid-here",
  "ideal_person": "Elon Musk",
  "favourite_celebrity": "Lionel Messi",
  "celebrity_to_talk": null,
  "created_at": "2026-04-08T..."
}
```

### 2. Chat with Agent
```
POST /api/chat
Body:
{
  "session_id": "uuid-from-session",
  "message": "What do you think about football?"
}
Response:
{
  "session_id": "uuid",
  "response": "AI response in celebrity style...",
  "personas": ["Elon Musk", "Lionel Messi"]
}
```

### 3. Health Check
```
GET /health
Response: {"status": "ok", "message": "Backend is running"}
```

## How It Works

1. User fills welcome screen → `POST /api/session` saves their choices
2. User sends message → `POST /api/chat` triggers the LangGraph agent
3. Agent flow:
   - **Fetch Tweets Node**: Gets recent tweets for chosen celebrities
   - **Generate Reply Node**: Builds prompt with tweets + chat history → calls Hugging Face LLM
   - **Save Messages Node**: Saves conversation to Neon DB
4. Response returned to frontend in celebrity's voice

## Project Structure

```
eluminate-backend/
├── app/
│   ├── agents/
│   │   └── persona_agent.py    # LangGraph agent graph
│   ├── db/
│   │   └── database.py          # Neon DB connection pool
│   ├── models/
│   │   └── schemas.py           # Pydantic models
│   ├── routers/
│   │   ├── sessions.py          # Session endpoints
│   │   └── chat.py              # Chat endpoints
│   ├── services/
│   │   ├── llm_service.py       # Hugging Face LLM calls
│   │   ├── session_service.py   # Database operations
│   │   └── tweet_service.py     # Tweet fetching
│   ├── config.py                # Environment config
│   └── utils/                   # Helper functions
├── main.py                      # FastAPI app entry point
├── requirements.txt
├── .env
└── schema.sql                   # DB schema (for reference)
```
"# luminate-rag-backend" 
