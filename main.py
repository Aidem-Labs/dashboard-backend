from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from jose import jwt, JWTError
from app.config import settings
from app.db.database import init_db, close_pool
from app.routers import sessions, chat, documents, doc_chat, auth, therapy_chat, crisis
from app.routers import learning as learning_router
from app.models.schemas import FeedbackRequest
from app.services.learning_service import learning_service
from dotenv import load_dotenv

load_dotenv()
bearer_scheme = HTTPBearer()


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def require_admin(payload: dict = Depends(require_auth)):
    if not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Database initialized successfully!")
    yield
    await close_pool()


app = FastAPI(
    title="LMN8 Ketamine Therapy AI System",
    description="RAG-based ketamine therapy assistant with admin dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes
app.include_router(auth.router)
app.include_router(doc_chat.router)
app.include_router(chat.router)
app.include_router(therapy_chat.router)

# All other routes require auth
app.include_router(sessions.router, dependencies=[Depends(require_auth)])
app.include_router(documents.router, dependencies=[Depends(require_auth)])
app.include_router(crisis.router, dependencies=[Depends(require_auth)])

# Admin-only routes
app.include_router(learning_router.router, dependencies=[Depends(require_admin)])


# Only negative feedback goes to the learning queue for admin review
@app.post("/api/learning/feedback", tags=["learning"], dependencies=[Depends(require_auth)])
async def submit_feedback_public(request: FeedbackRequest):
    if request.feedback == "negative":
        await learning_service.add_to_queue(request)
    return {"status": "success", "message": "Feedback submitted"}


@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
