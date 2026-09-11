"""
Module phân tích ensemble: percentile, độ bất định, cảnh báo cực đoan.
Bao gồm hàm phân loại hiện tượng thời tiết theo QCVN 46:2012/BTNMT & WMO.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from config import ALERT_THRESHOLDS, ALERT_PROB_THRESHOLD, RAIN_THRESHOLDS


# ============================================================
# THỐNG KÊ ENSEMBLE
# ============================================================
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


# ============================================================
# XÁC SUẤT VƯỢT NGƯỠNG
# ============================================================
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
        prob_high = probability_exceed(
            temp_ensemble, ALERT_THRESHOLDS["temp_high"], "above"
        )
        for t, p in prob_high.items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "temp_high",
                    "label": f"Nắng nóng (T > {ALERT_THRESHOLDS['temp_high']}°C)",
                    "time": t,
                    "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["temp_high"],
                    "value_mean": float(temp_ensemble.loc[t].mean()),
                })

        prob_low = probability_exceed(
            temp_ensemble, ALERT_THRESHOLDS["temp_low"], "below"
        )
        for t, p in prob_low.items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "temp_low",
                    "label": f"Rét (T < {ALERT_THRESHOLDS['temp_low']}°C)",
                    "time": t,
                    "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["temp_low"],
                    "value_mean": float(temp_ensemble.loc[t].mean()),
                })

    if precip_ensemble is not None and not precip_ensemble.empty:
        prob_rain = probability_exceed(
            precip_ensemble, ALERT_THRESHOLDS["rain_heavy_1h"], "above"
        )
        for t, p in prob_rain.items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "rain_heavy_1h",
                    "label": f"Mưa lớn 1h (> {ALERT_THRESHOLDS['rain_heavy_1h']} mm)",
                    "time": t,
                    "probability": float(p),
                    "threshold": ALERT_THRESHOLDS["rain_heavy_1h"],
                    "value_mean": float(precip_ensemble.loc[t].mean()),
                })

        daily = precip_ensemble.resample("1D").sum()
        prob_daily = probability_exceed(
            daily, ALERT_THRESHOLDS["rain_heavy_24h"], "above"
        )
        for t, p in prob_daily.items():
            if p >= ALERT_PROB_THRESHOLD:
                alerts.append({
                    "type": "rain_heavy_24h",
                    "label": f"Mưa rất lớn 24h (> {ALERT_THRESHOLDS['rain_heavy_24h']} mm)",
                    "time": t,
                    "probability": float(p),
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
# PHÂN LOẠI HIỆN TƯỢNG THỜI TIẾT THEO LƯỢNG MƯA
# Theo QCVN 46:2012/BTNMT & WMO:
# - Mưa nhẹ: ≤ 2.5 mm/h
# - Mưa vừa: 2.5 – 7.5 mm/h
# - Mưa to: 7.5 – 15 mm/h
# - Mưa rất to: > 15 mm/h (mưa lớn)
# ============================================================
def classify_weather_phenomenon(hour: int, rain_mm: float,
                                temp_c: float = None) -> str:
    """
    Phân loại hiện tượng thời tiết dựa trên lượng mưa và giờ.

    Parameters
    ----------
    hour : int
        Giờ trong ngày (0-23)
    rain_mm : float
        Lượng mưa trong 1 giờ (mm)
    temp_c : float, optional
        Nhiệt độ (°C) – dùng để phân biệt nắng nóng

    Returns
    -------
    str
        Mô tả hiện tượng kèm icon
    """
    is_night = (hour < 6) or (hour >= 18)
    moon = " 🌙" if is_night else ""

    t_trace = RAIN_THRESHOLDS["rain_trace"]
    t_light = RAIN_THRESHOLDS["rain_light"]
    t_mod = RAIN_THRESHOLDS["rain_moderate"]
    t_heavy = RAIN_THRESHOLDS["rain_heavy"]

    if rain_mm > t_heavy:
        return f"⛈️ Mưa rất to{moon}"
    elif rain_mm > t_mod:
        return f"🌧️ Mưa to{moon}"
    elif rain_mm > t_light:
        return f"🌦️ Mưa vừa{moon}"
    elif rain_mm > t_trace:
        return f"🌦️ Mưa nhẹ{moon}"
    elif rain_mm > 0.01:
        return f"☁️ Nhiều mây{moon}"

    # Không mưa
    if is_night:
        return "🌙 Trời trong"
    else:
        if temp_c is not None and temp_c >= 35.0:
            return "☀️ Nắng nóng"
        return "☀️ Nắng"


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