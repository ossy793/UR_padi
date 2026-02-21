# backend/main.py
"""
AI Health Partner – FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from core.config import settings
from db.session import engine, Base

# Import all models so Base.metadata knows about them
from models import user  # noqa: F401
from models import daily_questions as dq_models  # noqa: F401

# Route imports
from api.routes import (
    auth,
    users,
    predictions,
    health_scores,
    mental,
    gamification,
    payments,
    websocket,
    daily_questions,
)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered health risk prediction and prevention platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],   # Loosen for hackathon demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: Create DB tables ─────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"\n✅ {settings.APP_NAME} started. Tables created.")
    print("\n📋 Registered API routes:")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            m = list(route.methods)[0] if route.methods else "     "
            print(f"   {m:7s} {route.path}")

    daily_routes = [r.path for r in app.routes if "daily" in getattr(r, "path", "")]
    if daily_routes:
        print(f"\n✅ Daily Questions routes loaded OK: {daily_routes}")
    else:
        print("\n❌ CRITICAL: Daily Questions routes NOT registered!")
        print("   → Make sure you replaced ALL files from the new ZIP")
    print()


# ── API Routes ────────────────────────────────────────────────────────────────
API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)
app.include_router(health_scores.router, prefix=API_PREFIX)
app.include_router(mental.router, prefix=API_PREFIX)
app.include_router(gamification.router, prefix=API_PREFIX)
app.include_router(payments.router, prefix=API_PREFIX)
app.include_router(daily_questions.router, prefix=API_PREFIX)
app.include_router(websocket.router)   # WebSocket has its own path


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}