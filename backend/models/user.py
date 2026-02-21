# backend/models/user.py
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Health profile
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    genotype = Column(String(10), nullable=True)  # AA, AS, SS, AC
    blood_group = Column(String(10), nullable=True)  # A+, B-, O+, etc.
    family_history = Column(JSON, nullable=True)    # {"hypertension": true, "diabetes": false}
    pre_existing_conditions = Column(JSON, nullable=True)  # ["asthma", "diabetes"]
    location = Column(String(200), nullable=True)

    # Account
    is_premium = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    streak_days = Column(Integer, default=0)
    points = Column(Integer, default=0)
    last_checkin = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    health_scores = relationship("HealthScore", back_populates="user", cascade="all, delete")
    predictions = relationship("RiskPrediction", back_populates="user", cascade="all, delete")
    checkins = relationship("MentalCheckin", back_populates="user", cascade="all, delete")
    payments = relationship("Payment", back_populates="user", cascade="all, delete")


class HealthScore(Base):
    __tablename__ = "health_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Score components (0–10 each)
    sleep_score = Column(Float, nullable=False)
    diet_score = Column(Float, nullable=False)
    activity_score = Column(Float, nullable=False)
    mental_score = Column(Float, nullable=False)

    # Composite score (0–100)
    composite_score = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="health_scores")


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    prediction_type = Column(String(50), nullable=False)  # "hypertension" | "malaria"
    risk_percentage = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)       # "low" | "medium" | "high"
    claude_explanation = Column(Text, nullable=True)
    prevention_advice = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="predictions")


class MentalCheckin(Base):
    __tablename__ = "mental_checkins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    text_input = Column(Text, nullable=False)
    sentiment = Column(String(50), nullable=True)    # positive / neutral / negative
    emotional_state = Column(String(100), nullable=True)
    coping_suggestions = Column(Text, nullable=True)
    claude_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="checkins")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    reference = Column(String(200), unique=True, nullable=False)
    amount = Column(Float, nullable=False)   # in Naira
    status = Column(String(50), default="pending")   # pending | success | failed
    paystack_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")
