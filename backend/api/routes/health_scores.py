# backend/api/routes/health_scores.py
from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from models.user import User, HealthScore
from schemas.user import HealthScoreCreate, HealthScoreOut
from api.deps import get_current_user
from tasks.background import award_checkin_points

router = APIRouter(prefix="/health-scores", tags=["Health Scores"])


def _compute_composite(s: HealthScoreCreate) -> float:
    """Weighted composite: sleep 25%, diet 25%, activity 30%, mental 20%."""
    return round(
        (s.sleep_score * 2.5) + (s.diet_score * 2.5) + (s.activity_score * 3.0) + (s.mental_score * 2.0),
        1,
    )


@router.post("/", response_model=HealthScoreOut, status_code=201)
async def submit_health_score(
    payload: HealthScoreCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    composite = _compute_composite(payload)
    score = HealthScore(
        user_id=current_user.id,
        sleep_score=payload.sleep_score,
        diet_score=payload.diet_score,
        activity_score=payload.activity_score,
        mental_score=payload.mental_score,
        composite_score=composite,
    )
    db.add(score)
    await db.commit()
    await db.refresh(score)

    background_tasks.add_task(award_checkin_points, current_user.id, current_user.username, db)
    return score


@router.get("/", response_model=List[HealthScoreOut])
async def get_health_scores(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthScore)
        .where(HealthScore.user_id == current_user.id)
        .order_by(HealthScore.recorded_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
