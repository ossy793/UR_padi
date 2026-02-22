# ⚕ URPadi- AI Health Partner

A full-stack AI health platform featuring:
- ML-powered risk prediction (Hypertension & Malaria)
- Claude AI explanation layer
- Weekly health scoring with Chart.js visualisation
- Real-time WebSocket updates
- Gamification (streaks, points, leaderboard)
- Mental health check-in with sentiment analysis
- Location-based malaria risk map (Leaflet.js)
- Paystack premium payment integration

---

## 🗂 Project Structure

```
URPadi/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── core/
│   │   ├── config.py             # Settings & env vars
│   │   └── security.py           # JWT + password hashing
│   ├── db/
│   │   └── session.py            # Async SQLAlchemy engine
│   ├── models/
│   │   └── user.py               # ORM models
│   ├── schemas/
│   │   └── user.py               # Pydantic schemas
│   ├── api/
│   │   ├── deps.py               # Auth dependencies
│   │   └── routes/
│   │       ├── auth.py           # Register & login
│   │       ├── users.py          # Profile management
│   │       ├── predictions.py    # AI risk prediction
│   │       ├── health_scores.py  # Weekly score tracking
│   │       ├── mental.py         # Mental health check-in
│   │       ├── gamification.py   # Points & leaderboard
│   │       ├── payments.py       # Paystack integration
│   │       └── websocket.py      # Real-time WS endpoint
│   ├── services/
│   │   └── claude_service.py     # Claude AI integration
│   ├── ml/
│   │   ├── predictor.py          # Random Forest engine
│   │   └── models/               # .pkl model files (generated)
│   ├── utils/
│   │   └── redis_client.py       # Redis cache + leaderboard
│   └── tasks/
│       └── background.py         # Streak & notification tasks
├── frontend/
│   ├── index.html                # Single-page app
│   └── js/
│       └── app.js                # All frontend logic
├── scripts/
│   └── train_models.py           # ML model training script
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Local Setup Instructions

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+ running locally
- Redis 7+ running locally
- Node not required (no build step)

### 2. Clone & Install

```bash
git clone <your-repo>
cd ai-health-partner

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual values:
#   - DATABASE_URL (your PostgreSQL connection string)
#   - REDIS_URL
#   - ANTHROPIC_API_KEY (get from console.anthropic.com)
#   - PAYSTACK_SECRET_KEY (get from dashboard.paystack.com)
```

### 4. Set Up PostgreSQL

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE health_partner;"

# Tables are auto-created on first startup (SQLAlchemy creates_all)
```

### 5. Start Redis

```bash
# macOS (Homebrew)
brew services start redis

# Linux
sudo systemctl start redis-server

# Windows (WSL or Redis for Windows)
redis-server
```

### 6. Train ML Models

```bash
# Generate and save Random Forest models to backend/ml/models/
python scripts/train_models.py

# Output:
# ✅ hypertension_model.pkl saved
# ✅ malaria_model.pkl saved
```

### 7. Run the Application

```bash
# From project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 8. Open the App

Open `frontend/index.html` directly in your browser, **or** visit:
```
http://localhost:8000/
```
(FastAPI serves the frontend at the root path)

### API Docs
```
http://localhost:8000/api/docs     ← Swagger UI
http://localhost:8000/api/redoc    ← ReDoc
```

---

## 🔑 Key Features

### AI Risk Prediction
- POST `/api/predictions/` with `{ "prediction_type": "hypertension" | "malaria" }`
- Returns probability, risk level, Claude explanation, and prevention advice
- Results cached in Redis for 10 minutes

### Health Score
- Submit daily scores (sleep/diet/activity/mental, 0–10 each)
- Composite score (0–100) calculated and stored
- Visual chart in dashboard

### Mental Check-in
- Text or simulated voice input
- Claude assesses sentiment, emotional state, and provides coping strategies

### Gamification
- +10 points per check-in
- +50 bonus every 7-day streak
- Leaderboard powered by Redis Sorted Sets

### Paystack Integration (Demo)
- POST `/api/payments/initiate` — creates payment session
- POST `/api/payments/verify` — verifies and activates premium
- Works in demo mode without live Paystack keys

---

## 🧪 Demo Credentials

Register with any email/password to get started. The app works fully in demo mode without payment keys or a real Claude API key (falls back to sensible placeholder responses).

---

## 🌍 Environment Variables Reference

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://…`) |
| `SYNC_DATABASE_URL` | Sync URL for Alembic |
| `REDIS_URL` | Redis connection (`redis://localhost:6379/0`) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `PAYSTACK_SECRET_KEY` | Paystack secret key |
| `PAYSTACK_PUBLIC_KEY` | Paystack public key (for frontend) |
| `SECRET_KEY` | JWT signing secret (change in production!) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL (default 1440 = 24h) |
