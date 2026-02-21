"""
diagnose.py  –  Run this from the project root to find what's broken.

Usage:
    python diagnose.py
"""
import sys, os
print("\n" + "="*60)
print("  AI Health Partner – Diagnostic Tool")
print("="*60 + "\n")

errors = []
warnings = []

# ── 1. Python version ────────────────────────────────────────
v = sys.version_info
print(f"[1] Python {v.major}.{v.minor}.{v.micro}", end="  ")
if v.major < 3 or (v.major == 3 and v.minor < 9):
    errors.append("Python 3.9+ required")
    print("❌  (need 3.9+)")
else:
    print("✅")

# ── 2. Working directory ─────────────────────────────────────
cwd = os.getcwd()
print(f"[2] CWD: {cwd}", end="  ")
expected = ["backend", "frontend", "requirements.txt"]
missing  = [f for f in expected if not os.path.exists(f)]
if missing:
    errors.append(f"Missing from CWD: {missing}  — run from the project root folder!")
    print(f"❌  missing: {missing}")
else:
    print("✅")

# ── 3. .env file ────────────────────────────────────────────
print(f"[3] .env file", end="  ")
if not os.path.exists(".env"):
    errors.append(".env file missing — copy .env.example to .env and fill in your values")
    print("❌  (not found)")
else:
    print("✅")

# ── 4. Check packages ────────────────────────────────────────
packages = ["fastapi", "uvicorn", "sqlalchemy", "groq", "pydantic", "passlib", "jose"]
for pkg in packages:
    print(f"[4] import {pkg}", end="  ")
    try:
        __import__(pkg)
        print("✅")
    except ImportError as e:
        errors.append(f"Package '{pkg}' not installed — run: pip install -r requirements.txt")
        print(f"❌  ({e})")

# ── 5. Check all backend files exist ────────────────────────
files = [
    "backend/main.py",
    "backend/api/routes/daily_questions.py",
    "backend/models/daily_questions.py",
    "backend/services/question_service.py",
    "backend/tasks/background.py",
]
for f in files:
    print(f"[5] {f}", end="  ")
    if os.path.exists(f):
        print("✅")
    else:
        errors.append(f"Missing file: {f}")
        print("❌")

# ── 6. Check daily_questions is in main.py ───────────────────
print("[6] daily_questions registered in main.py", end="  ")
try:
    main_content = open("backend/main.py").read()
    if "daily_questions" in main_content and "include_router(daily_questions" in main_content:
        print("✅")
    else:
        errors.append("daily_questions router NOT registered in backend/main.py")
        print("❌")
except Exception as e:
    print(f"❌  ({e})")

# ── 7. Try importing the daily_questions route ───────────────
print("[7] Import daily_questions route", end="  ")
sys.path.insert(0, ".")
try:
    # Load .env first
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    from backend.api.routes import daily_questions as dq
    routes = [r.path for r in dq.router.routes]
    print(f"✅  routes: {routes}")
except Exception as e:
    errors.append(f"daily_questions import FAILED: {e}")
    print(f"❌  {e}")
    import traceback
    traceback.print_exc()

# ── 8. Test DB connection ────────────────────────────────────
print("[8] PostgreSQL connection", end="  ")
try:
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL","").replace("+asyncpg","")
    if not db_url:
        raise Exception("DATABASE_URL not set in .env")
    import psycopg2
    conn = psycopg2.connect(db_url, connect_timeout=3)
    conn.close()
    print("✅")
except Exception as e:
    warnings.append(f"DB connection failed: {e}")
    print(f"⚠️   {e}")

# ── Summary ──────────────────────────────────────────────────
print("\n" + "="*60)
if errors:
    print(f"  ❌ {len(errors)} ERROR(S) FOUND:")
    for i, e in enumerate(errors, 1):
        print(f"     {i}. {e}")
else:
    print("  ✅ No errors found! The server should work.")
    print("     Run: python -m uvicorn backend.main:app --reload --port 8000")

if warnings:
    print(f"\n  ⚠️  {len(warnings)} WARNING(S):")
    for w in warnings:
        print(f"     • {w}")

print("="*60 + "\n")