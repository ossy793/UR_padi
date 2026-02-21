# backend/api/routes/mental.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from models.user import User, MentalCheckin
from schemas.user import MentalCheckinCreate, MentalCheckinOut
from api.deps import get_current_user
from services.claude_service import assess_mental_health

router = APIRouter(prefix="/mental", tags=["Mental Health"])


@router.post("/checkin", response_model=MentalCheckinOut, status_code=201)
async def mental_checkin(
    payload: MentalCheckinCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Send to Claude for assessment
    assessment = await assess_mental_health(payload.text_input, current_user.username)

    checkin = MentalCheckin(
        user_id=current_user.id,
        text_input=payload.text_input,
        sentiment=assessment.get("sentiment"),
        emotional_state=assessment.get("emotional_state"),
        coping_suggestions=assessment.get("coping"),
        claude_response=assessment.get("full_response"),
    )
    db.add(checkin)
    await db.commit()
    await db.refresh(checkin)
    return checkin


@router.get("/checkins", response_model=List[MentalCheckinOut])
async def get_checkins(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MentalCheckin)
        .where(MentalCheckin.user_id == current_user.id)
        .order_by(MentalCheckin.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()
