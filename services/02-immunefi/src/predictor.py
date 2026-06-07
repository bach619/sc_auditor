"""BountyPredictor — Prediksi perubahan bounty menggunakan heuristics + ML.

Level 1: Heuristic-based prediction (regression rules)
Level 2: Statistical model (moving averages, trend detection)
Level 3: ML model (XGBoost/RandomForest — pluggable via joblib)

Saat ini menggunakan Level 1+2. Untuk Level 3, train model
terpisah dan simpan di /models/bounty_predictor.pkl.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.models import Program
from src.storage import EnhancedJSONStorage


class BountyPredictor:
    """Prediksi arah perubahan bounty.

    Menggunakan historical data (history/{slug}.jsonl) untuk
    mendeteksi tren dan memprediksi perubahan.
    """

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage
        self._model = None  # lazy load untuk ML model

    # ── ML Model (optional) ────────────────────────────────

    def _load_model(self):
        """Load trained ML model dari disk (jika ada)."""
        if self._model is not None:
            return self._model

        model_path = Path("/models/bounty_predictor.pkl")
        if model_path.exists():
            try:
                import joblib  # noqa: PLC0415
                self._model = joblib.load(model_path)
                return self._model
            except Exception:
                pass
        return None

    # ── Feature Extraction ─────────────────────────────────

    def _extract_features(self, program: Program) -> dict[str, float]:
        """Extract features untuk prediction.

        Sama seperti yang digunakan waktu training ML model.
        """
        return {
            "current_bounty": float(program.max_bounty or 0),
            "total_contracts": float(len(program.contracts)),
            "total_repos": float(len(program.repos)),
            "chain_count": float(len(program.chains)),
            "is_active": 1.0 if program.status.lower() in ("active", "live") else 0.0,
        }

    # ── Heuristic Prediction ──────────────────────────────

    async def predict(self, program: Program) -> dict[str, Any]:
        """Prediksi apakah bounty akan naik/turun dalam 30 hari.

        Returns dict dengan probability, confidence, dan rationale.
        """
        slug = program.slug
        features = self._extract_features(program)
        history = self.storage.get_history(slug, limit=10)

        # Deteksi tren dari history
        trend = self._detect_trend(history)
        volatility = self._calc_volatility(history)
        recency = self._recency_score(program)

        # Heuristic scoring
        will_increase_prob = self._calc_increase_probability(
            features=features,
            trend=trend,
            volatility=volatility,
            recency=recency,
        )

        # Try ML model if available
        ml_prediction = None
        model = self._load_model()
        if model is not None:
            try:
                import pandas as pd  # noqa: PLC0415
                df = pd.DataFrame([features])
                ml_prediction = float(model.predict_proba(df)[0][1])
                # Blend heuristic + ML
                will_increase_prob = (will_increase_prob * 0.4) + (ml_prediction * 0.6)
            except Exception:
                pass

        will_increase = will_increase_prob > 0.6

        # Estimated new bounty
        current = program.max_bounty or 0
        if will_increase:
            estimated_new = current * (1 + will_increase_prob * 0.5)
        else:
            estimated_new = current * (1 - (1 - will_increase_prob) * 0.3)

        # Confidence
        if abs(will_increase_prob - 0.5) > 0.3:
            confidence = "high"
        elif abs(will_increase_prob - 0.5) > 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        reasons = self._generate_reasons(
            features=features,
            trend=trend,
            will_increase=will_increase,
        )

        return {
            "slug": slug,
            "program_name": program.name,
            "current_bounty": current,
            "will_increase": will_increase,
            "probability": round(will_increase_prob, 3),
            "confidence": confidence,
            "estimated_new_bounty": round(estimated_new, 2),
            "estimated_change_pct": round(
                (estimated_new - current) / current * 100 if current > 0 else 0,
                1,
            ),
            "trend_direction": trend.get("direction", "stable"),
            "trend_strength": round(trend.get("strength", 0), 2),
            "volatility": round(volatility, 2),
            "reasons": reasons,
            "ml_model_used": model is not None,
            "predicted_at": datetime.now(UTC).isoformat(),
        }

    # ── Internal ──────────────────────────────────────────

    def _detect_trend(self, history: list[dict]) -> dict:
        """Deteksi tren bounty dari history entries.

        Returns {direction: "up"|"down"|"stable", strength: 0-1}.
        """
        if len(history) < 2:
            return {"direction": "stable", "strength": 0}

        bounties = []
        for entry in history:
            snapshot = entry.get("snapshot") or entry.get("new_value") or {}
            bounty = snapshot.get("max_bounty")
            if bounty is not None:
                try:
                    bounties.append(float(bounty))
                except (ValueError, TypeError):
                    pass

        if len(bounties) < 2:
            return {"direction": "stable", "strength": 0}

        # Simple linear regression slope
        n = len(bounties)
        x_avg = (n - 1) / 2
        y_avg = sum(bounties) / n

        num = sum((i - x_avg) * (b - y_avg) for i, b in enumerate(bounties))
        den = sum((i - x_avg) ** 2 for i in range(n))

        slope = num / den if den != 0 else 0
        max_b = max(bounties) if bounties else 1
        norm_slope = slope / max_b if max_b > 0 else 0

        if norm_slope > 0.05:
            direction = "up"
        elif norm_slope < -0.05:
            direction = "down"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "strength": min(abs(norm_slope) * 10, 1.0),
            "slope": slope,
        }

    def _calc_volatility(self, history: list[dict]) -> float:
        """Hitung volatilitas bounty dari history."""
        bounties = []
        for entry in history:
            snapshot = entry.get("snapshot") or entry.get("new_value") or {}
            bounty = snapshot.get("max_bounty")
            if bounty is not None:
                try:
                    bounties.append(float(bounty))
                except (ValueError, TypeError):
                    pass

        if len(bounties) < 2:
            return 0

        mean = sum(bounties) / len(bounties)
        if mean == 0:
            return 0
        variance = sum((b - mean) ** 2 for b in bounties) / len(bounties)
        return math.sqrt(variance) / mean  # coefficient of variation

    def _recency_score(self, program: Program) -> float:
        """Skor berdasarkan seberapa baru update."""
        if not program.updated_at:
            return 0.5
        try:
            updated = datetime.fromisoformat(program.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            days = (datetime.now(UTC) - updated).days
            if days < 7:
                return 1.0
            elif days < 30:
                return 0.8
            elif days < 90:
                return 0.5
            elif days < 365:
                return 0.2
            return 0.0
        except Exception:
            return 0.5

    def _calc_increase_probability(
        self,
        features: dict,
        trend: dict,
        volatility: float,
        recency: float,
    ) -> float:
        """Calculate probability of bounty increase."""
        prob = 0.5  # baseline

        # Trend
        if trend["direction"] == "up":
            prob += trend["strength"] * 0.2
        elif trend["direction"] == "down":
            prob -= trend["strength"] * 0.15

        # Bounty size: smaller bounties more likely to increase
        bounty = features["current_bounty"]
        if 0 < bounty < 10_000:
            prob += 0.1
        elif bounty >= 1_000_000:
            prob -= 0.05  # already high

        # More contracts = more complexity = more likely to increase bounty
        if features["total_contracts"] >= 5:
            prob += 0.05

        # Active programs more likely to update
        if features["is_active"]:
            prob += 0.1

        # Recently updated programs
        prob += recency * 0.1

        # Volatility: moderate volatility = healthy program
        if 0.1 < volatility < 0.5:
            prob += 0.05
        elif volatility > 0.8:
            prob -= 0.1  # too volatile

        return max(0.05, min(0.95, prob))

    def _generate_reasons(
        self,
        features: dict,
        trend: dict,
        will_increase: bool,
    ) -> list[str]:
        """Generate human-readable reasons for prediction."""
        reasons = []

        if trend["direction"] == "up":
            reasons.append(f"Bounty trending upward (strength: {trend['strength']:.2f})")
        elif trend["direction"] == "down":
            reasons.append(f"Bounty trending downward (strength: {trend['strength']:.2f})")

        bounty = features["current_bounty"]
        if 0 < bounty < 10_000:
            reasons.append("Low current bounty — room for increase")
        elif bounty >= 1_000_000:
            reasons.append("Already at high bounty — less room for increase")

        if features["total_contracts"] >= 5:
            reasons.append(f"Complex project ({int(features['total_contracts'])} contracts)")

        if features["is_active"]:
            reasons.append("Program is active — likely to update")

        return reasons
