# backend/schemas/user.py
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    genotype: Optional[str] = None
    blood_group: Optional[str] = None
    family_history: Optional[Dict[str, bool]] = None
    pre_existing_conditions: Optional[List[str]] = None
    location: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    is_premium: bool


# ── Profile ───────────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    id: int
    email: str
    username: str
    age: Optional[int]
    gender: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    genotype: Optional[str]
    blood_group: Optional[str]
    family_history: Optional[Dict[str, bool]]
    pre_existing_conditions: Optional[List[str]]
    location: Optional[str]
    is_premium: bool
    streak_days: int
    points: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    genotype: Optional[str] = None
    blood_group: Optional[str] = None
    family_history: Optional[Dict[str, bool]] = None
    pre_existing_conditions: Optional[List[str]] = None
    location: Optional[str] = None


# ── Health Score ──────────────────────────────────────────────────────────────

class HealthScoreCreate(BaseModel):
    sleep_score: float       # 0–10
    diet_score: float        # 0–10
    activity_score: float    # 0–10
    mental_score: float      # 0–10

    @field_validator("sleep_score", "diet_score", "activity_score", "mental_score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(10.0, v))


class HealthScoreOut(BaseModel):
    id: int
    sleep_score: float
    diet_score: float
    activity_score: float
    mental_score: float
    composite_score: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# ── Risk Prediction ───────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    prediction_type: str  # "hypertension" | "malaria"


class PredictionOut(BaseModel):
    id: int
    prediction_type: str
    risk_percentage: float
    risk_level: str
    claude_explanation: Optional[str]
    prevention_advice: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Mental Check-in ───────────────────────────────────────────────────────────

class MentalCheckinCreate(BaseModel):
    text_input: str


class MentalCheckinOut(BaseModel):
    id: int
    text_input: str
    sentiment: Optional[str]
    emotional_state: Optional[str]
    coping_suggestions: Optional[str]
    claude_response: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Leaderboard ───────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    points: int


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentInitiate(BaseModel):
    amount: float = 5000.0   # NGN


class PaymentVerify(BaseModel):
    reference: str
