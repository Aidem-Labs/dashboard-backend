from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class CreateSessionRequest(BaseModel):
    onboarding_data: dict[str, Any] = {}


class SessionResponse(BaseModel):
    id: UUID
    onboarding_data: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: UUID
    message: str


class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    personas: list[str]
    sources: list[str] = []


class FeedbackRequest(BaseModel):
    question: str
    ai_answer: str
    feedback: str  # 'positive' or 'negative'
    suggested_answer: Optional[str] = None


class LearningQueueItem(BaseModel):
    id: UUID
    question: str
    ai_answer: Optional[str]
    feedback: Optional[str]
    suggested_answer: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Auth Schemas ---

class UserCreate(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OTPVerify(BaseModel):
    email: str
    code: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_verified: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
