 # backend/api/routes/gamification.py
from typing import List
from fastapi import APIRouter, Depends

from models.user import User
from schemas.user import LeaderboardEntry
from api.deps import get_current_user
from utils.redis_client import leaderboard_top

router = APIRouter(prefix="/gamification", tags=["Gamification"])


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(_: User = Depends(get_current_user)):
    """Return top 20 users ranked by points from Redis sorted set."""
    return await leaderboard_top(20)


@router.get("/me/stats")
async def my_stats(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "points": current_user.points,
        "streak_days": current_user.streak_days,
        "is_premium": current_user.is_premium,
    }
