# backend/utils/redis_client.py
"""
Redis client with full graceful fallback.
If Redis is not running, all operations silently no-op.
The app works fully without Redis — caching and leaderboard
are simply disabled until Redis becomes available.
"""

import json
import logging
from typing import Optional, Any

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger("redis_client")

# Singleton Redis pool
_redis: Optional[aioredis.Redis] = None
_redis_available: bool = True   # Flips to False after first failed connection


async def get_redis() -> Optional[aioredis.Redis]:
    """
    Returns a Redis client, or None if Redis is unavailable.
    Once a connection failure is detected, skips reconnect attempts
    for the lifetime of the process (avoids log spam).
    """
    global _redis, _redis_available

    if not _redis_available:
        return None

    try:
        if _redis is None:
            _redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,   # Fast timeout so app doesn't hang
            )
        # Quick health check
        await _redis.ping()
        return _redis
    except Exception as e:
        _redis_available = False
        _redis = None
        logger.warning(
            f"[Redis] Not available ({e}). "
            "Caching and leaderboard features disabled. "
            "Start Redis to enable them."
        )
        return None


# ── Generic cache helpers ─────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = 600) -> None:
    """Serialize value to JSON and store with TTL (seconds). No-op if Redis is down."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


async def cache_get(key: str) -> Optional[Any]:
    """Return deserialized value or None. Returns None if Redis is down."""
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_delete(key: str) -> None:
    """Delete a key. No-op if Redis is down."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


# ── Leaderboard (Sorted Set) ──────────────────────────────────────────────────

LEADERBOARD_KEY = "health:leaderboard"


async def leaderboard_add(username: str, points: int) -> None:
    """Upsert user score in leaderboard. No-op if Redis is down."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.zadd(LEADERBOARD_KEY, {username: points})
    except Exception:
        pass


async def leaderboard_top(n: int = 20) -> list[dict]:
    """Return top-N users. Returns empty list if Redis is down."""
    r = await get_redis()
    if r is None:
        return []
    try:
        results = await r.zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True)
        return [
            {"rank": idx + 1, "username": username, "points": int(score)}
            for idx, (username, score) in enumerate(results)
        ]
    except Exception:
        return []


# ── Streak helpers ────────────────────────────────────────────────────────────

async def increment_points(username: str, delta: int) -> None:
    """Increment points in leaderboard. No-op if Redis is down."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.zincrby(LEADERBOARD_KEY, delta, username)
    except Exception:
        pass