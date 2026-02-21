# backend/tasks/background.py
"""
FastAPI background tasks:
- Streak maintenance
- Notification simulation
- Points award
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from utils.redis_client import leaderboard_add, increment_points

logger = logging.getLogger("background_tasks")


async def award_checkin_points(user_id: int, username: str, db: AsyncSession) -> None:
    """
    Award points after a health check-in and update streak.
    Called as a FastAPI BackgroundTask.
    """
    from sqlalchemy import update
    from models.user import User

    now = datetime.utcnow()
    points_earned = 10

    # Fetch user
    result = await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    # Update streak
    if user.last_checkin and (now - user.last_checkin) < timedelta(hours=48):
        new_streak = user.streak_days + 1
    else:
        new_streak = 1

    # Streak bonus
    if new_streak % 7 == 0:
        points_earned += 50
        logger.info(f"[streak] {username} hit a {new_streak}-day streak! Bonus 50 pts.")

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            streak_days=new_streak,
            points=User.points + points_earned,
            last_checkin=now,
        )
    )
    await db.commit()

    # Sync to Redis leaderboard — silently skip if Redis is unavailable
    try:
        await increment_points(username, points_earned)
    except Exception:
        pass
    logger.info(f"[points] {username} earned {points_earned} pts. Streak: {new_streak}d")


async def send_health_reminder(username: str, message: str = "") -> None:
    """
    Simulated push notification / reminder.
    In production this would call FCM, email, or SMS gateway.
    """
    if not message:
        message = f"Hi {username}! Don't forget your daily health check-in. Keep your streak alive! 🏃"
    logger.info(f"[notification] → {username}: {message}")