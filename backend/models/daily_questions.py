# backend/models/daily_questions.py
"""
ORM models for the AI-generated daily gamified health questions system.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from db.session import Base


class DailyQuestionSet(Base):
    """
    Stores a generated set of questions for a specific calendar date.
    Questions rotate daily — one set per date, shared by all users.
    """
    __tablename__ = "daily_question_sets"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)   # e.g. 2026-02-21
    questions = Column(JSON, nullable=False)                        # Full question set JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    responses = relationship("DailyQuestionResponse", back_populates="question_set", cascade="all, delete")


class DailyQuestionResponse(Base):
    """
    Stores a user's answers to a daily question set.
    One row per user per day.
    """
    __tablename__ = "daily_question_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_set_id = Column(Integer, ForeignKey("daily_question_sets.id"), nullable=False)

    date = Column(Date, nullable=False, index=True)
    answers = Column(JSON, nullable=False)          # {"q_id": "selected_option_value", ...}

    # Computed category scores (0–10 each) — hidden from user in API
    sleep_score = Column(Float, nullable=True)
    diet_score = Column(Float, nullable=True)
    activity_score = Column(Float, nullable=True)
    mental_score = Column(Float, nullable=True)
    location_score = Column(Float, nullable=True)

    # ML features extracted from answers (used for risk prediction)
    ml_features = Column(JSON, nullable=True)

    # Composite score (0–100)
    composite_score = Column(Float, nullable=True)

    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    question_set = relationship("DailyQuestionSet", back_populates="responses")