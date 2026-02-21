# backend/services/claude_service.py
"""
Groq API integration layer.
Uses Groq's ultra-fast inference with llama-3.3-70b-versatile model.
Provides:
  - Risk explanation + prevention advice
  - Mental health / emotional assessment
"""
import json
from typing import Optional

from groq import Groq

from core.config import settings

# Lazy client instantiation
_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _clean_json(raw: str) -> str:
    """Strip markdown code fences from model response if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        # parts[1] contains the content between first pair of fences
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ── Risk Explanation ──────────────────────────────────────────────────────────

async def explain_risk(
    prediction_type: str,
    risk_percentage: float,
    risk_level: str,
    user_context: dict,
) -> dict:
    """
    Send structured risk data to Groq.
    Returns: { "explanation": str, "prevention": str, "lifestyle": str }
    """
    prompt = f"""
You are a friendly, empathetic AI health assistant helping users understand their health risks.

A user has received the following risk assessment:
- Condition: {prediction_type.replace("_", " ").title()}
- Risk Score: {risk_percentage:.1f}%
- Risk Level: {risk_level.upper()}

User Profile:
- Age: {user_context.get("age", "unknown")}
- Gender: {user_context.get("gender", "unknown")}
- Genotype: {user_context.get("genotype", "unknown")}
- Pre-existing conditions: {", ".join(user_context.get("pre_existing_conditions") or ["none"])}
- Family history: {json.dumps(user_context.get("family_history") or {})}
- Location: {user_context.get("location", "unknown")}

Respond ONLY with valid JSON — no extra text, no markdown fences. Use exactly these keys:
{{
  "explanation": "A friendly 2-3 sentence explanation of what this risk score means for this specific user",
  "prevention": "3-5 concrete, actionable prevention tips tailored to their profile",
  "lifestyle": "2-3 lifestyle changes they can start today"
}}

Be warm, encouraging, and specific. Avoid medical jargon.
"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful health assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        raw = response.choices[0].message.content
        return json.loads(_clean_json(raw))
    except Exception as e:
        # Graceful fallback so the app keeps working without a valid API key
        return {
            "explanation": f"Your {prediction_type} risk is {risk_level} at {risk_percentage:.1f}%. Please consult a healthcare professional for personalised guidance.",
            "prevention": "Maintain a balanced diet, exercise regularly, stay hydrated, avoid smoking, and schedule regular check-ups.",
            "lifestyle": "Start with 30 minutes of walking daily and reduce processed food intake.",
        }


# ── Mental Health Assessment ──────────────────────────────────────────────────

async def assess_mental_health(text_input: str, username: str) -> dict:
    """
    Analyse a text check-in for emotional state and provide coping suggestions.
    Returns: { "sentiment": str, "emotional_state": str, "coping": str, "full_response": str }
    """
    prompt = f"""
You are a compassionate AI mental wellness companion. A user named {username} has shared how they are feeling:

"{text_input}"

Respond ONLY with valid JSON — no extra text, no markdown fences. Use exactly these keys:
{{
  "sentiment": "positive | neutral | negative",
  "emotional_state": "A short label like 'anxious', 'hopeful', 'stressed', 'content', etc.",
  "coping": "3-4 evidence-based coping strategies personalised to what they shared",
  "full_response": "A warm, 2-3 sentence empathetic response acknowledging their feelings"
}}

Be supportive, non-judgmental, and encourage professional help if the text suggests serious distress.
"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a compassionate mental wellness assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        raw = response.choices[0].message.content
        return json.loads(_clean_json(raw))
    except Exception as e:
        return {
            "sentiment": "neutral",
            "emotional_state": "reflective",
            "coping": "Try deep breathing exercises, journaling your thoughts, taking a short walk, or talking to a trusted friend.",
            "full_response": "Thank you for sharing how you feel. It takes courage to check in with yourself. You are not alone.",
        }

# ── Health Overview Explanation ───────────────────────────────────────────────

async def explain_health_overview(
    overall_score: int,
    risks: dict,
    risk_areas: list,
    strengths: list,
    user_context: dict,
) -> dict:
    """
    Generate a personalized health overview narrative using Groq AI.
    Returns: { "summary": str, "recommendations": str, "encouragement": str }
    """
    top_risks_str = ", ".join(
        f"{r['condition']} ({r['percentage']:.0f}% risk)" for r in risk_areas[:3]
    ) if risk_areas else "no critical risks identified"

    strengths_str = ", ".join(strengths[:3]) if strengths else "working on building healthy habits"

    region = user_context.get("regional_context", {}).get("region", "Africa")
    country = user_context.get("regional_context", {}).get("country", "")

    prompt = f"""
You are a warm, expert African health advisor providing a personalised health overview.

USER PROFILE:
- Age: {user_context.get('age', 'unknown')}
- Gender: {user_context.get('gender', 'unknown')}
- BMI: {user_context.get('bmi', 'unknown')}
- Genotype: {user_context.get('genotype', 'unknown')}
- Blood Group: {user_context.get('blood_group', 'unknown')}
- Location: {user_context.get('location', 'Africa')} ({region})
- Family History: {json.dumps(user_context.get('family_history') or {})}
- Lifestyle Scores: {json.dumps(user_context.get('lifestyle', {}))}

ANALYSIS RESULTS:
- Overall Health Score: {overall_score}/100
- Top Risk Areas: {top_risks_str}
- Health Strengths: {strengths_str}
- Regional Context: {country or region} — consider local disease patterns and healthcare access

Respond ONLY with valid JSON — no markdown, no extra text. Use exactly these keys:
{{
  "summary": "A warm, personalized 3-4 sentence health overview narrative. Acknowledge their specific profile, mention their top 2 risk areas by name, and reference their regional health context. Avoid alarm — be empowering.",
  "recommendations": "4-6 specific, actionable prevention steps tailored to their risk profile and African health context. Mention diet, activity, screening, and region-specific precautions. Make them practical.",
  "encouragement": "A 1-2 sentence motivating closing message that affirms their proactive health monitoring and encourages continued engagement."
}}

Be culturally sensitive to African contexts. Mention accessible healthcare options where relevant.
"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful African health advisor. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=900,
            temperature=0.7,
        )
        raw = response.choices[0].message.content
        return json.loads(_clean_json(raw))
    except Exception as e:
        return {
            "summary": f"Your health overview score is {overall_score}/100. Based on your profile and regional health data, we've identified key areas to monitor including {top_risks_str}. Your strengths include {strengths_str}.",
            "recommendations": "Stay physically active with at least 30 minutes daily. Maintain a balanced diet rich in vegetables and whole grains. Schedule regular blood pressure and blood sugar checks. Use insecticide-treated bed nets if in a malaria-endemic area. Stay hydrated and avoid processed foods.",
            "encouragement": "You're taking a proactive approach to your health — that's the most powerful step you can take. Keep monitoring and stay consistent!",
        }


# ── Mental Health Assessment ──────────────────────────────────────────────────

async def assess_mental_health(text_input: str, username: str) -> dict:
    """
    Analyse a text check-in for emotional state and provide coping suggestions.
    Returns: { "sentiment": str, "emotional_state": str, "coping": str, "full_response": str }
    """
    prompt = f"""
You are a compassionate AI mental wellness companion. A user named {username} has shared how they are feeling:

"{text_input}"

Respond ONLY with valid JSON — no extra text, no markdown fences. Use exactly these keys:
{{
  "sentiment": "positive | neutral | negative",
  "emotional_state": "A short label like 'anxious', 'hopeful', 'stressed', 'content', etc.",
  "coping": "3-4 evidence-based coping strategies personalised to what they shared",
  "full_response": "A warm, 2-3 sentence empathetic response acknowledging their feelings"
}}

Be supportive, non-judgmental, and encourage professional help if the text suggests serious distress.
"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a compassionate mental wellness assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        raw = response.choices[0].message.content
        return json.loads(_clean_json(raw))
    except Exception:
        return {
            "sentiment": "neutral",
            "emotional_state": "reflective",
            "coping": "Try deep breathing exercises, journaling your thoughts, taking a short walk, or talking to a trusted friend.",
            "full_response": "Thank you for sharing how you feel. It takes courage to check in with yourself. You are not alone.",
        }


# ── Legacy wrapper kept for backward compatibility ────────────────────────────

async def explain_risk(
    prediction_type: str,
    risk_percentage: float,
    risk_level: str,
    user_context: dict,
) -> dict:
    """Legacy single-disease explanation — routes to overview explainer."""
    risks     = {prediction_type: risk_percentage}
    risk_areas = [{"condition": prediction_type, "percentage": risk_percentage, "level": risk_level}]
    strengths  = []
    result = await explain_health_overview(
        overall_score=max(0, int(100 - risk_percentage)),
        risks=risks,
        risk_areas=risk_areas,
        strengths=strengths,
        user_context=user_context,
    )
    return {
        "explanation": result.get("summary", ""),
        "prevention":  result.get("recommendations", ""),
        "lifestyle":   result.get("encouragement", ""),
    }