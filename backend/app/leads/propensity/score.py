"""Real-time scoring service for lead conversion propensity."""

from pathlib import Path
from typing import Any
import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"

_CACHED_MODEL = None


def get_model():
    global _CACHED_MODEL
    if _CACHED_MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}. Run train.py first.")
        _CACHED_MODEL = joblib.load(MODEL_PATH)
    return _CACHED_MODEL


def predict_propensity(lead_data: dict[str, Any]) -> dict[str, Any]:
    """Scores an incoming lead profile for conversion propensity.

    Args:
        lead_data: dict with keys:
            - employee_count (int)
            - num_sites or sites (int)
            - monthly_telecom_spend_inr or monthly_spend (int)
            - business_type (str)
            - city_tier or tier (int)
            - has_gstin (bool or str)
            - current_provider (str)
            - current_internet (str)
            - segment (str)

    Returns:
        dict: {
            "score": float (0.0 to 1.0),
            "score_int": int (0 to 100),
            "decile": int (1 to 10),
            "band": str ("HIGH" | "MEDIUM" | "LOW"),
            "model_version": "1.0.0",
            "top_factors": list[str]
        }
    """
    model = get_model()

    # Normalize fields
    emp = int(lead_data.get("employee_count") or lead_data.get("employees") or 3)
    sites = int(lead_data.get("num_sites") or lead_data.get("sites") or 1)
    spend = int(lead_data.get("monthly_telecom_spend_inr") or lead_data.get("monthly_spend") or 1500)
    b_type = str(lead_data.get("business_type") or "Bakery")
    tier = int(lead_data.get("city_tier") or lead_data.get("tier") or 2)
    has_gst = 1 if lead_data.get("has_gstin") in (True, "Y", "true", 1) else 0
    prov = str(lead_data.get("current_provider") or "Competitor A")
    net = str(lead_data.get("current_internet") or "Home broadband")
    seg = str(lead_data.get("segment") or "micro")

    row = pd.DataFrame([{
        "employee_count": emp,
        "num_sites": sites,
        "monthly_telecom_spend_inr": spend,
        "business_type": b_type,
        "city_tier": tier,
        "has_gstin_num": has_gst,
        "current_provider": prov,
        "current_internet": net,
        "segment": seg,
    }])

    prob = float(model.predict_proba(row)[0, 1])
    score_int = int(round(prob * 100.0))

    # Decile mapping based on empirical score distribution (baseline CR ~7.4%)
    if prob >= 0.15:
        decile = 10
        band = "HIGH"
    elif prob >= 0.12:
        decile = 9
        band = "HIGH"
    elif prob >= 0.09:
        decile = 8
        band = "MEDIUM"
    elif prob >= 0.07:
        decile = 7
        band = "MEDIUM"
    elif prob >= 0.06:
        decile = 6
        band = "MEDIUM"
    elif prob >= 0.05:
        decile = 5
        band = "LOW"
    elif prob >= 0.04:
        decile = 4
        band = "LOW"
    elif prob >= 0.03:
        decile = 3
        band = "LOW"
    elif prob >= 0.02:
        decile = 2
        band = "LOW"
    else:
        decile = 1
        band = "LOW"

    # Identify explanatory factors
    factors = []
    if sites > 1:
        factors.append(f"Multi-site deployment ({sites} branches)")
    if has_gst:
        factors.append("Active GST registered entity")
    if spend >= 3000:
        factors.append(f"High monthly telecom spend (INR {spend})")
    if emp >= 10:
        factors.append(f"Enterprise size ({emp} employees)")
    if not factors:
        factors.append(f"Standard single-site {b_type}")

    return {
        "score": round(prob, 4),
        "score_int": score_int,
        "decile": decile,
        "band": band,
        "model_version": "1.0.0",
        "top_factors": factors,
    }
