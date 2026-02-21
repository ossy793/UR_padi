# backend/api/routes/predictions.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from models.user import User, RiskPrediction
from schemas.user import PredictionRequest, PredictionOut
from api.deps import get_current_user
from ml.predictor import predictor
from services.claude_service import explain_risk
from utils.redis_client import cache_get, cache_set
from tasks.background import award_checkin_points

router = APIRouter(prefix="/predictions", tags=["Risk Predictions"])


@router.post("/", response_model=PredictionOut, status_code=201)
async def create_prediction(
    payload: PredictionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.prediction_type not in ("hypertension", "malaria"):
        raise HTTPException(400, "prediction_type must be 'hypertension' or 'malaria'")

    # ── Cache check (10-minute TTL) ───────────────────────────────────────────
    cache_key = f"pred:{current_user.id}:{payload.prediction_type}"
    cached = await cache_get(cache_key)
    if cached:
        # Return the latest stored prediction for this type
        result = await db.execute(
            select(RiskPrediction)
            .where(
                RiskPrediction.user_id == current_user.id,
                RiskPrediction.prediction_type == payload.prediction_type,
            )
            .order_by(RiskPrediction.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    # ── Run ML prediction ─────────────────────────────────────────────────────
    user_context = {
        "age": current_user.age,
        "gender": current_user.gender,
        "height_cm": current_user.height_cm,
        "weight_kg": current_user.weight_kg,
        "genotype": current_user.genotype,
        "blood_group": current_user.blood_group,
        "family_history": current_user.family_history,
        "pre_existing_conditions": current_user.pre_existing_conditions,
        "location": current_user.location,
    }
    risk_pct, risk_level = predictor.predict(payload.prediction_type, user_context)

    # ── Claude explanation ────────────────────────────────────────────────────
    claude_data = await explain_risk(
        payload.prediction_type, risk_pct, risk_level, user_context
    )

    # ── Persist ───────────────────────────────────────────────────────────────
    pred = RiskPrediction(
        user_id=current_user.id,
        prediction_type=payload.prediction_type,
        risk_percentage=risk_pct,
        risk_level=risk_level,
        claude_explanation=claude_data.get("explanation"),
        prevention_advice=(
            claude_data.get("prevention", "") + "\n\n" + claude_data.get("lifestyle", "")
        ),
    )
    db.add(pred)
    await db.commit()
    await db.refresh(pred)

    # ── Cache result ──────────────────────────────────────────────────────────
    await cache_set(cache_key, {"risk_pct": risk_pct, "risk_level": risk_level}, ttl=600)

    # ── Award points in background ────────────────────────────────────────────
    background_tasks.add_task(award_checkin_points, current_user.id, current_user.username, db)

    return pred


@router.get("/", response_model=List[PredictionOut])
async def list_predictions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == current_user.id)
        .order_by(RiskPrediction.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
