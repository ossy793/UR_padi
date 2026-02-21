# backend/services/question_service.py
"""
AI-powered daily rotating gamified health question generator.

Uses Groq to generate a fresh set of 5–8 multiple-choice questions each day,
across 5 health categories. Questions rotate daily (seeded by date).
Scoring logic is hidden from users — only composite/category scores are shown.
"""
import json
import hashlib
from datetime import date
from typing import Optional

from groq import Groq
from core.config import settings

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ── Hardcoded fallback question bank ─────────────────────────────────────────
# Used when Groq is unavailable. 30+ questions rotated by date hash.

FALLBACK_QUESTION_BANK = [
    # DIET
    {
        "question_id": "d001", "category": "diet",
        "question_text": "🥗 How many servings of vegetables did you eat today?",
        "options": [
            {"label": "None at all 😬",       "value": 0},
            {"label": "1 serving",            "value": 1},
            {"label": "2–3 servings",         "value": 2},
            {"label": "4 or more! 🥦",        "value": 3},
        ],
        "feature_key": "veg_servings", "scoring_weight": 0.20,
    },
    {
        "question_id": "d002", "category": "diet",
        "question_text": "🧃 How many sugary drinks did you have today?",
        "options": [
            {"label": "None — water only 💧", "value": 3},
            {"label": "1 drink",              "value": 2},
            {"label": "2–3 drinks",           "value": 1},
            {"label": "4 or more 🥤",         "value": 0},
        ],
        "feature_key": "sugary_drinks", "scoring_weight": 0.15,
    },
    {
        "question_id": "d003", "category": "diet",
        "question_text": "🧂 How salty was your food today?",
        "options": [
            {"label": "Very salty 😬",         "value": 0},
            {"label": "Moderately salty",      "value": 1},
            {"label": "Lightly salted",        "value": 2},
            {"label": "No added salt 👍",      "value": 3},
        ],
        "feature_key": "salt_intake", "scoring_weight": 0.15,
    },
    {
        "question_id": "d004", "category": "diet",
        "question_text": "🍎 Did you eat any fruits today?",
        "options": [
            {"label": "No fruits today",       "value": 0},
            {"label": "1 piece of fruit",      "value": 1},
            {"label": "2–3 pieces 🍊",         "value": 2},
            {"label": "More than 3 pieces!",   "value": 3},
        ],
        "feature_key": "fruit_intake", "scoring_weight": 0.15,
    },
    {
        "question_id": "d005", "category": "diet",
        "question_text": "💧 How much water did you drink today?",
        "options": [
            {"label": "Less than 1 litre 😬",  "value": 0},
            {"label": "1–2 litres",            "value": 1},
            {"label": "2–3 litres 👍",         "value": 2},
            {"label": "More than 3 litres 💪", "value": 3},
        ],
        "feature_key": "water_intake", "scoring_weight": 0.20,
    },
    {
        "question_id": "d006", "category": "diet",
        "question_text": "🫘 Did you eat iron-rich foods today? (beans, spinach, liver)",
        "options": [
            {"label": "No",                    "value": 0},
            {"label": "A small amount",        "value": 1},
            {"label": "Yes, a good portion 💪","value": 2},
        ],
        "feature_key": "iron_rich_foods", "scoring_weight": 0.15,
    },
    # SLEEP
    {
        "question_id": "s001", "category": "sleep",
        "question_text": "🌙 How many hours did you sleep last night?",
        "options": [
            {"label": "Less than 4 hours 😴",  "value": 0},
            {"label": "4–5 hours",             "value": 1},
            {"label": "6–7 hours",             "value": 2},
            {"label": "7–9 hours 🌟",          "value": 3},
        ],
        "feature_key": "sleep_hours", "scoring_weight": 0.35,
    },
    {
        "question_id": "s002", "category": "sleep",
        "question_text": "😴 How restful was your sleep?",
        "options": [
            {"label": "Very poor — woke up many times", "value": 0},
            {"label": "Average — some disruptions",     "value": 1},
            {"label": "Good — mostly uninterrupted",    "value": 2},
            {"label": "Excellent — felt fully rested ✨","value": 3},
        ],
        "feature_key": "sleep_quality", "scoring_weight": 0.35,
    },
    {
        "question_id": "s003", "category": "sleep",
        "question_text": "📵 Did you use your phone in bed before sleeping?",
        "options": [
            {"label": "Yes, for 1+ hour",       "value": 0},
            {"label": "Yes, 30–60 minutes",     "value": 1},
            {"label": "Yes, under 30 minutes",  "value": 2},
            {"label": "No screens at all 🌙",   "value": 3},
        ],
        "feature_key": "phone_before_sleep", "scoring_weight": 0.15,
    },
    # ACTIVITY
    {
        "question_id": "a001", "category": "activity",
        "question_text": "🏃 How much physical activity did you do today?",
        "options": [
            {"label": "None at all 🛋️",           "value": 0},
            {"label": "Light — short walk/stretch", "value": 1},
            {"label": "Moderate — 30 min exercise", "value": 2},
            {"label": "Intense — 1hr+ workout 💪",  "value": 3},
        ],
        "feature_key": "exercise_level", "scoring_weight": 0.40,
    },
    {
        "question_id": "a002", "category": "activity",
        "question_text": "🪑 How many hours did you sit/stay sedentary today?",
        "options": [
            {"label": "More than 10 hours 😬",  "value": 0},
            {"label": "7–10 hours",             "value": 1},
            {"label": "4–6 hours",              "value": 2},
            {"label": "Less than 4 hours 🏆",   "value": 3},
        ],
        "feature_key": "sedentary_hours", "scoring_weight": 0.30,
    },
    {
        "question_id": "a003", "category": "activity",
        "question_text": "🚶 Did you take the stairs or walk instead of using transport today?",
        "options": [
            {"label": "No, not at all",          "value": 0},
            {"label": "Once or twice",           "value": 1},
            {"label": "Several times",           "value": 2},
            {"label": "Yes, I walked most places 🎯", "value": 3},
        ],
        "feature_key": "incidental_activity", "scoring_weight": 0.30,
    },
    # MENTAL
    {
        "question_id": "m001", "category": "mental",
        "question_text": "🧠 How would you rate your stress level today?",
        "options": [
            {"label": "Extremely stressed 😰",   "value": 0},
            {"label": "Quite stressed",          "value": 1},
            {"label": "Mild stress",             "value": 2},
            {"label": "Calm and relaxed 😌",     "value": 3},
        ],
        "feature_key": "stress_level", "scoring_weight": 0.35,
    },
    {
        "question_id": "m002", "category": "mental",
        "question_text": "😊 Overall, how was your mood today?",
        "options": [
            {"label": "Very low / sad",          "value": 0},
            {"label": "Low / flat",              "value": 1},
            {"label": "Okay / neutral",          "value": 2},
            {"label": "Good / positive 🌟",      "value": 3},
        ],
        "feature_key": "mood_level", "scoring_weight": 0.35,
    },
    {
        "question_id": "m003", "category": "mental",
        "question_text": "🤝 Did you connect with friends, family, or loved ones today?",
        "options": [
            {"label": "No social interaction",   "value": 0},
            {"label": "Brief interaction",       "value": 1},
            {"label": "Some quality time",       "value": 2},
            {"label": "Great social connection 💙","value": 3},
        ],
        "feature_key": "social_connection", "scoring_weight": 0.30,
    },
    # LOCATION / ENVIRONMENT
    {
        "question_id": "l001", "category": "location",
        "question_text": "🌿 How was the air quality around you today?",
        "options": [
            {"label": "Very polluted / smoky 😷",   "value": 0},
            {"label": "Some pollution",             "value": 1},
            {"label": "Average air quality",        "value": 2},
            {"label": "Clean / fresh air 🌬️",       "value": 3},
        ],
        "feature_key": "air_quality", "scoring_weight": 0.40,
    },
    {
        "question_id": "l002", "category": "location",
        "question_text": "🦟 Did you sleep under a mosquito net or use repellent last night?",
        "options": [
            {"label": "No protection at all",      "value": 0},
            {"label": "Partial protection",        "value": 1},
            {"label": "Yes, used repellent",       "value": 2},
            {"label": "Yes, mosquito net + repellent 💪","value": 3},
        ],
        "feature_key": "mosquito_protection", "scoring_weight": 0.35,
    },
    {
        "question_id": "l003", "category": "location",
        "question_text": "🚿 How was your access to clean water today?",
        "options": [
            {"label": "No clean water access",     "value": 0},
            {"label": "Limited access",            "value": 1},
            {"label": "Good access",               "value": 2},
            {"label": "Full clean water access 💧","value": 3},
        ],
        "feature_key": "clean_water_access", "scoring_weight": 0.25,
    },
]

# Category to question mapping
CATEGORY_QUESTIONS = {
    "diet":     [q for q in FALLBACK_QUESTION_BANK if q["category"] == "diet"],
    "sleep":    [q for q in FALLBACK_QUESTION_BANK if q["category"] == "sleep"],
    "activity": [q for q in FALLBACK_QUESTION_BANK if q["category"] == "activity"],
    "mental":   [q for q in FALLBACK_QUESTION_BANK if q["category"] == "mental"],
    "location": [q for q in FALLBACK_QUESTION_BANK if q["category"] == "location"],
}


def _pick_daily_questions(target_date: date) -> list:
    """
    Select 5–8 questions rotated by date using a deterministic hash.
    Each category gets 1–2 questions. Same date always returns same set.
    """
    seed = int(hashlib.md5(str(target_date).encode()).hexdigest(), 16)

    selected = []
    for category, questions in CATEGORY_QUESTIONS.items():
        # Pick 1 or 2 questions per category depending on available count
        count = min(2 if len(questions) >= 2 else 1, len(questions))
        # Deterministic shuffle based on date seed
        shuffled = sorted(questions, key=lambda q: (seed ^ hash(q["question_id"])) % 9999)
        selected.extend(shuffled[:count])

    return selected


# ── Groq AI question generation ───────────────────────────────────────────────

async def generate_daily_questions(target_date: date) -> list:
    """
    Use Groq to generate fresh daily questions.
    Falls back to hardcoded bank if Groq is unavailable.
    """
    prompt = f"""
You are a health gamification expert designing daily check-in questions for a health app.

Today's date: {target_date.strftime("%A, %B %d, %Y")}
Date seed for rotation: {target_date.toordinal()}

Generate exactly 7 short, engaging, gamified multiple-choice health questions for today.
Use these categories (at least 1 per category):
- diet (2 questions)
- sleep (1 question)
- activity (2 questions)
- mental (1 question)
- location (1 question)

Rules:
- Questions must be answerable in under 30 seconds
- Use emojis to make them fun and engaging
- Options must have 3–4 choices
- Options must be ordered from worst to best health outcome
- Each option has a hidden numeric value (0=worst, 1, 2, 3=best) — DO NOT show values to user
- Vary questions based on the date seed so they feel fresh each day

Respond ONLY with a valid JSON array. No extra text. Format:
[
  {{
    "question_id": "d001",
    "category": "diet",
    "question_text": "🥗 How many servings of vegetables did you eat today?",
    "options": [
      {{"label": "None at all 😬", "value": 0}},
      {{"label": "1 serving", "value": 1}},
      {{"label": "2–3 servings", "value": 2}},
      {{"label": "4 or more! 🥦", "value": 3}}
    ],
    "feature_key": "veg_servings",
    "scoring_weight": 0.20
  }}
]
"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a health gamification expert. Respond with valid JSON arrays only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.8,
        )
        raw = response.choices[0].message.content.strip()
        # Clean markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        questions = json.loads(raw.strip())
        # Validate structure
        if isinstance(questions, list) and len(questions) >= 5:
            return questions
    except Exception:
        pass

    # Fallback to hardcoded bank
    return _pick_daily_questions(target_date)


# ── Score calculation (server-side, hidden from user) ─────────────────────────

def calculate_scores(questions: list, answers: dict) -> dict:
    """
    Calculate category and composite scores from user answers.
    answers: { "question_id": selected_value (int) }
    Returns scores and ML features — scoring logic never sent to frontend.
    """
    category_totals = {}   # category -> [weighted_score, total_weight]
    ml_features = {}

    for q in questions:
        qid = q["question_id"]
        category = q["category"]
        weight = q.get("scoring_weight", 0.20)
        feature_key = q.get("feature_key", qid)

        if qid not in answers:
            continue

        # Find the max value in options for normalisation
        option_values = [opt["value"] for opt in q["options"]]
        max_val = max(option_values) if option_values else 3
        raw_val = answers[qid]

        # Normalise to 0–1 range
        normalised = raw_val / max_val if max_val > 0 else 0

        # Store ML feature (raw value for model)
        ml_features[feature_key] = raw_val

        # Accumulate weighted score per category
        if category not in category_totals:
            category_totals[category] = [0, 0]
        category_totals[category][0] += normalised * weight
        category_totals[category][1] += weight

    # Compute 0–10 scores per category
    category_scores = {}
    for cat, (total, weight_sum) in category_totals.items():
        category_scores[cat] = round((total / weight_sum) * 10, 1) if weight_sum > 0 else 5.0

    # Map to standard names
    sleep_score    = category_scores.get("sleep",    5.0)
    diet_score     = category_scores.get("diet",     5.0)
    activity_score = category_scores.get("activity", 5.0)
    mental_score   = category_scores.get("mental",   5.0)
    location_score = category_scores.get("location", 5.0)

    # Weighted composite (0–100)
    composite = round(
        (sleep_score * 2.5) +
        (diet_score * 2.5) +
        (activity_score * 3.0) +
        (mental_score * 2.0) +
        (location_score * 0.0),  # location informs ML but not composite
        1
    )
    composite = min(100.0, composite)

    return {
        "sleep_score":    sleep_score,
        "diet_score":     diet_score,
        "activity_score": activity_score,
        "mental_score":   mental_score,
        "location_score": location_score,
        "composite_score": composite,
        "ml_features":    ml_features,
    }