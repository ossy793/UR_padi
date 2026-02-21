# backend/ml/predictor.py
"""
Random Forest risk prediction engine.
Models are loaded from .pkl files once at startup.
Falls back to heuristic scoring if model files are not found.
"""
import os
import joblib
import numpy as np
from pathlib import Path
from typing import Tuple

MODEL_DIR = Path(__file__).parent / "models"


class RiskPredictor:
    def __init__(self):
        self.hypertension_model = self._load("hypertension_model.pkl")
        self.malaria_model = self._load("malaria_model.pkl")

    def _load(self, filename: str):
        path = MODEL_DIR / filename
        if path.exists():
            return joblib.load(path)
        print(f"[ML] Warning: {filename} not found — using heuristic fallback.")
        return None

    # ── Feature extraction ────────────────────────────────────────────────────

    def _hypertension_features(self, user: dict) -> np.ndarray:
        """
        Features: age, gender_enc, bmi, family_hypertension, diabetes, smoking
        """
        age = user.get("age") or 30
        gender = 1 if (user.get("gender") or "").lower() == "male" else 0
        h = user.get("height_cm") or 170
        w = user.get("weight_kg") or 70
        bmi = w / ((h / 100) ** 2)
        fh = user.get("family_history") or {}
        family_hyp = int(fh.get("hypertension", False))
        conditions = [c.lower() for c in (user.get("pre_existing_conditions") or [])]
        has_diabetes = int("diabetes" in conditions)
        genotype = user.get("genotype") or "AA"
        return np.array([[age, gender, bmi, family_hyp, has_diabetes, 0]])

    def _malaria_features(self, user: dict) -> np.ndarray:
        """
        Features: age, gender_enc, location_risk, genotype_ss, pre_malaria
        """
        age = user.get("age") or 30
        gender = 1 if (user.get("gender") or "").lower() == "male" else 0
        location = (user.get("location") or "").lower()
        # Simple heuristic: tropical/rural locations score higher
        tropical_keywords = ["lagos", "abuja", "kano", "ibadan", "rural", "north", "south", "east", "west", "nigeria", "ghana", "kenya"]
        loc_risk = int(any(k in location for k in tropical_keywords))
        genotype = (user.get("genotype") or "AA").upper()
        geno_ss = int(genotype == "SS")
        conditions = [c.lower() for c in (user.get("pre_existing_conditions") or [])]
        prev_malaria = int("malaria" in conditions)
        return np.array([[age, gender, loc_risk, geno_ss, prev_malaria]])

    # ── Heuristic fallback ────────────────────────────────────────────────────

    def _heuristic_hypertension(self, user: dict) -> float:
        score = 0.0
        age = user.get("age") or 30
        score += min(age / 100, 0.4)
        fh = user.get("family_history") or {}
        if fh.get("hypertension"):
            score += 0.2
        conditions = [c.lower() for c in (user.get("pre_existing_conditions") or [])]
        if "diabetes" in conditions:
            score += 0.15
        h = user.get("height_cm") or 170
        w = user.get("weight_kg") or 70
        bmi = w / ((h / 100) ** 2)
        if bmi > 30:
            score += 0.15
        return min(score, 0.95)

    def _heuristic_malaria(self, user: dict) -> float:
        score = 0.15
        location = (user.get("location") or "").lower()
        tropical = ["lagos", "abuja", "kano", "rural", "nigeria", "ghana", "kenya"]
        if any(k in location for k in tropical):
            score += 0.35
        genotype = (user.get("genotype") or "AA").upper()
        if genotype == "SS":
            score += 0.2
        conditions = [c.lower() for c in (user.get("pre_existing_conditions") or [])]
        if "malaria" in conditions:
            score += 0.15
        return min(score, 0.95)

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, prediction_type: str, user: dict) -> Tuple[float, str]:
        """
        Returns (risk_percentage: float 0-100, risk_level: str low|medium|high).
        """
        if prediction_type == "hypertension":
            if self.hypertension_model:
                features = self._hypertension_features(user)
                prob = self.hypertension_model.predict_proba(features)[0][1]
            else:
                prob = self._heuristic_hypertension(user)
        elif prediction_type == "malaria":
            if self.malaria_model:
                features = self._malaria_features(user)
                prob = self.malaria_model.predict_proba(features)[0][1]
            else:
                prob = self._heuristic_malaria(user)
        else:
            raise ValueError(f"Unknown prediction type: {prediction_type}")

        pct = round(prob * 100, 1)
        if pct < 30:
            level = "low"
        elif pct < 65:
            level = "medium"
        else:
            level = "high"

        return pct, level


# Singleton instance loaded once at startup
predictor = RiskPredictor()
