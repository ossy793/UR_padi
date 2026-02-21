# backend/api/routes/auth.py
import os
import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from models.user import User
from schemas.user import UserLogin, TokenResponse
from core.security import hash_password, verify_password, create_access_token
from utils.redis_client import leaderboard_add

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Directory where uploaded medical reports are saved
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads", "medical_reports")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed file types for medical reports
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}
MAX_FILE_SIZE_MB = 10


async def save_medical_report(file: UploadFile, user_id: int) -> str:
    """Save uploaded medical report to disk. Returns the unique filename."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"File type '{ext}' not allowed. Accepted: PDF, PNG, JPG, DOC, DOCX"
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large ({size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.")

    unique_name = f"user_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    return unique_name


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    # All fields sent as multipart/form-data so we can also accept a file
    email: str                   = Form(...),
    username: str                = Form(...),
    password: str                = Form(...),
    age: int                     = Form(None),
    gender: str                  = Form(None),
    height_cm: float             = Form(None),
    weight_kg: float             = Form(None),
    genotype: str                = Form(None),
    blood_group: str             = Form(None),
    location: str                = Form(None),
    family_history: str          = Form(None),        # JSON string: '{"hypertension":true}'
    pre_existing_conditions: str = Form(None),        # JSON string: '["diabetes"]'
    medical_report: UploadFile   = File(None),        # Optional file upload
    db: AsyncSession             = Depends(get_db),
):
    # Check uniqueness
    existing = await db.execute(
        select(User).where(
            (User.email == email) | (User.username == username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already registered.")

    # Parse JSON string fields safely
    fh = None
    if family_history:
        try:
            fh = json.loads(family_history)
        except Exception:
            fh = None

    pec = None
    if pre_existing_conditions:
        try:
            pec = json.loads(pre_existing_conditions)
        except Exception:
            pec = None

    # Create user first (we need the ID for the filename)
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        age=age,
        gender=gender,
        height_cm=height_cm,
        weight_kg=weight_kg,
        genotype=genotype,
        blood_group=blood_group,
        family_history=fh,
        pre_existing_conditions=pec,
        location=location,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Handle optional medical report upload
    if medical_report and medical_report.filename:
        try:
            report_filename = await save_medical_report(medical_report, user.id)
            user.medical_report_path = report_filename
            await db.commit()
        except HTTPException:
            raise
        except Exception:
            pass  # Don't fail registration over a file error

    # Seed leaderboard — silently skip if Redis is unavailable
    try:
        await leaderboard_add(user.username, 0)
    except Exception:
        pass

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_premium=user.is_premium,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_premium=user.is_premium,
    )


@router.get("/medical-report/{filename}", tags=["Authentication"])
async def download_medical_report(filename: str, db: AsyncSession = Depends(get_db)):
    """Download a user's own uploaded medical report."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found.")
    return FastAPIFileResponse(file_path, filename=filename)