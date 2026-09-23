"""
Module phân tích ensemble + phân loại hiện tượng QCVN.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from config import (
    ALERT_THRESHOLDS, ALERT_PROB_THRESHOLD,
    RAIN_THRESHOLDS, RAIN_THRESHOLDS_1H, RAIN_THRESHOLDS_24H,
)


def compute_ensemble_stats(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    stats = pd.DataFrame(index=df.index)
    stats["mean"] = df.mean(axis=1)
    stats["median"] = df.median(axis=1)
    stats["min"] = df.min(axis=1)
    stats["max"] = df.max(axis=1)
    stats["p10"] = df.quantile(0.10, axis=1)
    stats["p25"] = df.quantile(0.25, axis=1)
    stats["p75"] = df.quantile(0.75, axis=1)
    stats["p90"] = df.quantile(0.90, axis=1)
    stats["std"] = df.std(axis=1)
    stats["n_members"] = df.notna().sum(axis=1)
    return stats


def compute_median_ensemble(ensembles_dict: dict) -> pd.DataFrame:
    """Gộp tất cả thành viên từ nhiều mô hình → median ensemble."""
    if not ensembles_dict:
        return pd.DataFrame()

    all_members = []
    for mk, df in ensembles_dict.items():
        if df is None or df.empty:
            continue
        df_r = df.copy()
        df_r.columns = [f"{mk}_{c}" for c in df.columns]
        all_members.append(df_r)

    if not all_members:
        return pd.DataFrame()

    combined = pd.concat(all_members, axis=1)
    out = pd.DataFrame(index=combined.index)
    out["median"] = combined.median(axis=1)
    out["mean"] = combined.mean(axis=1)
    out["p10"] = combined.quantile(0.10, axis=1)
    out["p25"] = combined.quantile(0.25, axis=1)
    out["p75"] = combined.quantile(0.75, axis=1)
    out["p90"] = combined.quantile(0.90, axis=1)
    out["n_members"] = combined.notna().sum(axis=1)
    return out


def probability_exceed(df: pd.DataFrame, threshold: float,
                       direction: str = "above") -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    if direction == "above":
        prob = (df > threshold).sum(axis=1) / df.notna().sum(axis=1)
    else:
        prob = (df < threshold).sum(axis=1) / df.notna().sum(axis=1)
    return prob.replace([np.inf, -np.inf], np.nan)


def detect_extreme_events(temp_ensemble: Optional[pd.DataFrame],
                          precip_ensemble: Optional[pd.DataFrame]) -> List[Dict]:
    alerts = []
    if temp_ensemble is not None and not temp_ensemble.empty:
        for t, p in probability_exceed(
            temp_ensemble, ALERT_THRESHOLDS["temp_high"], "above"
        ).items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "temp_high",
                    "label": f"Nắng nóng (T > {ALERT_THRESHOLDS['temp_high']}°C)",
                    "time": t, "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["temp_high"],
                    "value_mean": float(temp_ensemble.loc[t].mean()),
                })
        for t, p in probability_exceed(
            temp_ensemble, ALERT_THRESHOLDS["temp_low"], "below"
        ).items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "temp_low",
                    "label": f"Rét (T < {ALERT_THRESHOLDS['temp_low']}°C)",
                    "time": t, "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["temp_low"],
                    "value_mean": float(temp_ensemble.loc[t].mean()),
                })

    if precip_ensemble is not None and not precip_ensemble.empty:
        for t, p in probability_exceed(
            precip_ensemble, ALERT_THRESHOLDS["rain_heavy_1h"], "above"
        ).items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "rain_heavy_1h",
                    "label": f"Mưa lớn 1h (> {ALERT_THRESHOLDS['rain_heavy_1h']} mm)",
                    "time": t, "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["rain_heavy_1h"],
                    "value_mean": float(precip_ensemble.loc[t].mean()),
                })
        daily = precip_ensemble.resample("1D").sum()
        for t, p in probability_exceed(
            daily, ALERT_THRESHOLDS["rain_heavy_24h"], "above"
        ).items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "rain_heavy_24h",
                    "label": f"Mưa rất lớn 24h (> {ALERT_THRESHOLDS['rain_heavy_24h']} mm)",
                    "time": t, "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["rain_heavy_24h"],
                    "value_mean": float(daily.loc[t].mean()),
                })
    alerts.sort(key=lambda x: x["time"])
    return alerts


def deduplicate_alerts(alerts: List[Dict]) -> List[Dict]:
    if not alerts:
        return []
    deduped = []
    for a in alerts:
        if deduped and deduped[-1]["type"] == a["type"]:
            delta = (a["time"] - deduped[-1]["time"]).total_seconds() / 3600
            if delta <= 6:
                if a["probability"] > deduped[-1]["probability"]:
                    deduped[-1] = a
                continue
        deduped.append(a)
    return deduped


# ============================================================
# PHÂN LOẠI HIỆN TƯỢNG THEO QCVN 46:2012 & WMO
# ============================================================
def classify_weather_phenomenon(hour: int, rain_mm: float,
                                 temp_c: float = None) -> str:
    """
    Phân loại hiện tượng theo mưa 1h.
    Ngưỡng: 
      - Không mưa: 0 mm
      - Rất nhẹ: 0.1–0.5
      - Nhẹ: 0.5–2.5
      - Vừa: 2.5–7.5
      - To: 7.5–15
      - Rất to: 15–30
      - Đặc biệt to: > 30
    """
    is_night = (hour < 6) or (hour >= 18)
    moon = " 🌙" if is_night else ""
    r = float(rain_mm) if rain_mm is not None else 0.0

    if r > 30.0:
        return f"🌊 Mưa đặc biệt to{moon}"
    elif r > 15.0:
        return f"⛈️ Mưa rất to{moon}"
    elif r > 7.5:
        return f"🌧️ Mưa to{moon}"
    elif r > 2.5:
        return f"🌧️ Mưa vừa{moon}"
    elif r > 0.5:
        return f"🌦️ Mưa nhẹ{moon}"
    elif r > 0.1:
        return f"🌦️ Mưa rất nhẹ{moon}"
    elif r > 0.0:
        return f"☁️ Mưa phùn{moon}"

    if is_night:
        return "🌙 Trời trong, không mưa"
    if temp_c is not None and temp_c >= 35.0:
        return "☀️ Nắng nóng"
    elif temp_c is not None and temp_c >= 32.0:
        return "☀️ Nắng"
    return "🌤️ Trời trong"


def classify_rain_24h(rain_24h_mm: float) -> str:
    r = float(rain_24h_mm) if rain_24h_mm else 0.0
    if r > 100.0:
        return "🌊 Mưa đặc biệt to (>100mm/24h)"
    elif r > 50.0:
        return "⛈️ Mưa rất to (50-100mm/24h)"
    elif r > 25.0:
        return "🌧️ Mưa to (25-50mm/24h)"
    elif r > 5.0:
        return "🌧️ Mưa vừa (5-25mm/24h)"
    elif r > 0.1:
        return "🌦️ Mưa nhỏ (<5mm/24h)"
    return "☀️ Không mưa"


# ============================================================
# TÓM TẮT
# ============================================================
def summarize_temperature(stats: pd.DataFrame) -> Dict:
    if stats is None or stats.empty:
        return {}
    return {
        "max_mean": float(stats["mean"].max()),
        "min_mean": float(stats["mean"].min()),
        "time_max": str(stats["mean"].idxmax()),
        "time_min": str(stats["mean"].idxmin()),
        "max_abs": float(stats["max"].max()),
        "min_abs": float(stats["min"].min()),
        "avg_std": float(stats["std"].mean()),
    }


def summarize_precipitation(stats: pd.DataFrame) -> Dict:
    if stats is None or stats.empty:
        return {}
    return {
        "total_rain_mm": float(stats["mean"].sum()),
        "total_rain_p90_mm": float(stats["p90"].sum()),
        "peak_hourly_mm": float(stats["mean"].max()),
        "time_peak": str(stats["mean"].idxmax()),
        "avg_std": float(stats["std"].mean()),
    }