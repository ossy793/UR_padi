# backend/api/routes/daily_questions.py
"""
Daily gamified health question endpoints.

GET  /daily-questions/today      → Get today's question set (AI-generated, cached by date)
POST /daily-questions/submit     → Submit answers, get scores back
GET  /daily-questions/history    → Get past responses with scores
GET  /daily-questions/example    → Get a full example question set (no auth needed)
"""
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db.session import get_db
from models.daily_questions import DailyQuestionSet, DailyQuestionResponse
from models.user import HealthScore
from api.deps import get_current_user
from models.user import User
from services.question_service import generate_daily_questions, calculate_scores
from tasks.background import award_checkin_points

router = APIRouter(prefix="/daily-questions", tags=["Daily Questions"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnswerSubmit(BaseModel):
    answers: dict   # { "question_id": selected_value (int) }


class QuestionOut(BaseModel):
    question_id: str
    category: str
    question_text: str
    options: list       # [{"label": str, "value": HIDDEN}] — value stripped before sending
    feature_key: str    # exposed for frontend display only


class DailySetOut(BaseModel):
    date: str
    questions: List[QuestionOut]
    already_completed: bool


class ScoreResult(BaseModel):
    composite_score: float
    sleep_score: float
    diet_score: float
    activity_score: float
    mental_score: float
    location_score: float
    message: str
    badge: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_values(questions: list) -> list:
    """
    Remove hidden scoring values from options before sending to frontend.
    The label order (worst→best) is preserved for UX, values are hidden.
    """
    clean = []
    for q in questions:
        clean.append({
            "question_id": q["question_id"],
            "category": q["category"],
            "question_text": q["question_text"],
            "feature_key": q.get("feature_key", q["question_id"]),
            "options": [{"label": opt["label"]} for opt in q["options"]],
            # NOTE: scoring_weight intentionally excluded
        })
    return clean


def _resolve_answer_values(questions: list, raw_answers: dict) -> dict:
    """
    Convert frontend label-based answers back to numeric values.
    Frontend sends: { "q_id": "label_string" }
    Returns:        { "q_id": numeric_value }
    """
    resolved = {}
    label_to_value = {}

    for q in questions:
        qid = q["question_id"]
        label_to_value[qid] = {opt["label"]: opt["value"] for opt in q["options"]}

    for qid, answer in raw_answers.items():
        if isinstance(answer, int):
            resolved[qid] = answer
        elif isinstance(answer, str) and qid in label_to_value:
            resolved[qid] = label_to_value[qid].get(answer, 0)
        else:
            resolved[qid] = 0

    return resolved


def _score_to_badge(score: float) -> str:
    if score >= 85:  return "🏆 Health Champion"
    if score >= 70:  return "🌟 Wellness Star"
    if score >= 55:  return "💪 Making Progress"
    if score >= 40:  return "🌱 Getting Started"
    return "❤️ Keep Going"


def _score_to_message(score: float) -> str:
    if score >= 85:  return "Outstanding! You're crushing your health goals today!"
    if score >= 70:  return "Great job! You're building excellent health habits."
    if score >= 55:  return "Good effort! Small improvements add up over time."
    if score >= 40:  return "You've made a start — tomorrow is another chance to improve!"
    return "Every day is a new opportunity. You've got this! 💙"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today_questions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns today's AI-generated question set.
    Questions are generated once per day and cached in the database.
    Hidden scoring values are stripped before returning to the client.
    """
    today = date.today()

    # Check if user already completed today's questions
    existing_response = await db.execute(
        select(DailyQuestionResponse).where(
            DailyQuestionResponse.user_id == current_user.id,
            DailyQuestionResponse.date == today,
        )
    )
    user_response = existing_response.scalar_one_or_none()
    already_completed = user_response is not None and user_response.completed

    # Get or generate today's question set
    result = await db.execute(
        select(DailyQuestionSet).where(DailyQuestionSet.date == today)
    )
    question_set = result.scalar_one_or_none()

    if not question_set:
        # Generate new set for today
        questions = await generate_daily_questions(today)
        question_set = DailyQuestionSet(date=today, questions=questions)
        db.add(question_set)
        await db.commit()
        await db.refresh(question_set)

    return {
        "date": str(today),
        "question_set_id": question_set.id,
        "already_completed": already_completed,
        "questions": _strip_values(question_set.questions),
    }


@router.post("/submit")
async def submit_answers(
    payload: AnswerSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept user answers, calculate hidden scores, store result, return scores.
    Users see: composite score + category scores + badge.
    Users do NOT see: raw option values, scoring weights, or ML features.
    """
    today = date.today()

    # Prevent double submission
    existing = await db.execute(
        select(DailyQuestionResponse).where(
            DailyQuestionResponse.user_id == current_user.id,
            DailyQuestionResponse.date == today,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "You have already completed today's check-in! Come back tomorrow 🌅")

    # Get today's question set
    result = await db.execute(
        select(DailyQuestionSet).where(DailyQuestionSet.date == today)
    )
    question_set = result.scalar_one_or_none()
    if not question_set:
        raise HTTPException(404, "Today's questions not found. Please load them first.")

    # Resolve label answers → numeric values (server-side only)
    numeric_answers = _resolve_answer_values(question_set.questions, payload.answers)

    # Calculate all scores server-side (hidden from user)
    scores = calculate_scores(question_set.questions, numeric_answers)

    # Save response
    response = DailyQuestionResponse(
        user_id=current_user.id,
        question_set_id=question_set.id,
        date=today,
        answers=payload.answers,   # Store original labels (not values)
        sleep_score=scores["sleep_score"],
        diet_score=scores["diet_score"],
        activity_score=scores["activity_score"],
        mental_score=scores["mental_score"],
        location_score=scores["location_score"],
        composite_score=scores["composite_score"],
        ml_features=scores["ml_features"],
        completed=True,
    )
    db.add(response)

    # Also save to HealthScore table for chart compatibility
    health_score = HealthScore(
        user_id=current_user.id,
        sleep_score=scores["sleep_score"],
        diet_score=scores["diet_score"],
        activity_score=scores["activity_score"],
        mental_score=scores["mental_score"],
        composite_score=scores["composite_score"],
    )
    db.add(health_score)
    await db.commit()

    # Award points in background
    background_tasks.add_task(award_checkin_points, current_user.id, current_user.username, db)

    composite = scores["composite_score"]
    return {
        "composite_score": composite,
        "sleep_score":     scores["sleep_score"],
        "diet_score":      scores["diet_score"],
        "activity_score":  scores["activity_score"],
        "mental_score":    scores["mental_score"],
        "location_score":  scores["location_score"],
        "badge":   _score_to_badge(composite),
        "message": _score_to_message(composite),
        # ML features NOT returned to client
    }


@router.get("/history")
async def get_question_history(
    limit: int = 14,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return past daily question responses with scores (no ML features)."""
    result = await db.execute(
        select(DailyQuestionResponse)
        .where(DailyQuestionResponse.user_id == current_user.id)
        .order_by(DailyQuestionResponse.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "date":            str(r.date),
            "composite_score": r.composite_score,
            "sleep_score":     r.sleep_score,
            "diet_score":      r.diet_score,
            "activity_score":  r.activity_score,
            "mental_score":    r.mental_score,
        }
        for r in rows
    ]


@router.get("/example")
async def get_example_question_set():
    """
    Returns a fully documented example question set with ML feature mapping.
    Used for API documentation / hackathon demo. No auth required.
    """
    from backend.services.question_service import FALLBACK_QUESTION_BANK, calculate_scores

    example_questions = FALLBACK_QUESTION_BANK[:7]

    # Example answers (best possible)
    example_answers = {q["question_id"]: max(opt["value"] for opt in q["options"]) for q in example_questions}

    scores = calculate_scores(example_questions, example_answers)

    return {
        "description": "Example daily question set with ML feature mapping",
        "date": str(date.today()),
        "total_questions": len(example_questions),
        "question_set": [
            {
                "question_id":    q["question_id"],
                "category":       q["category"],
                "question_text":  q["question_text"],
                "options":        [{"label": opt["label"]} for opt in q["options"]],
                "feature_key":    q["feature_key"],
                "ml_description": f"Maps to numeric feature '{q['feature_key']}' (0–3 scale)",
                # scoring_weight is HIDDEN in real API — shown here for demo only
                "scoring_weight_demo": q["scoring_weight"],
            }
            for q in example_questions
        ],
        "example_scores": {
            "composite_score": scores["composite_score"],
            "category_scores": {
                "sleep":    scores["sleep_score"],
                "diet":     scores["diet_score"],
                "activity": scores["activity_score"],
                "mental":   scores["mental_score"],
            },
            "ml_features_extracted": scores["ml_features"],
            "note": "scoring_weight and ml_features are server-side only in production"
        }
    }