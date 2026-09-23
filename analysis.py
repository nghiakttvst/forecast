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


# ============================================================
# THỐNG KÊ ENSEMBLE
# ============================================================
def compute_ensemble_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Tính thống kê ensemble — an toàn với mọi dtype."""
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        # Ép numeric, bỏ cột không phải số
        df_num = df.apply(pd.to_numeric, errors="coerce")
        df_num = df_num.dropna(axis=1, how="all")
        if df_num.empty:
            return pd.DataFrame()

        stats = pd.DataFrame(index=df_num.index)
        stats["mean"] = df_num.mean(axis=1).astype(float)
        stats["median"] = df_num.median(axis=1).astype(float)
        stats["min"] = df_num.min(axis=1).astype(float)
        stats["max"] = df_num.max(axis=1).astype(float)
        stats["p10"] = df_num.quantile(0.10, axis=1).astype(float)
        stats["p25"] = df_num.quantile(0.25, axis=1).astype(float)
        stats["p75"] = df_num.quantile(0.75, axis=1).astype(float)
        stats["p90"] = df_num.quantile(0.90, axis=1).astype(float)
        stats["std"] = df_num.std(axis=1).astype(float)
        stats["n_members"] = df_num.notna().sum(axis=1).astype(int)

        # Bỏ dòng toàn NaN
        stats = stats.dropna(subset=["mean"], how="all")
        return stats
    except Exception as e:
        print(f"[STATS] Lỗi: {e}")
        return pd.DataFrame()


# ============================================================
# TỔ HỢP TRUNG VỊ (MEDIAN ENSEMBLE)
# ============================================================
def compute_median_ensemble(ensembles_dict: dict) -> pd.DataFrame:
    """
    Gộp tất cả thành viên từ nhiều mô hình → median ensemble.
    Ép kiểu số + align index an toàn để tránh lỗi Plotly.
    """
    if not ensembles_dict:
        return pd.DataFrame()

    all_members = []
    for mk, df in ensembles_dict.items():
        if df is None or df.empty:
            continue
        try:
            # Ép tất cả về numeric
            df_num = df.apply(pd.to_numeric, errors="coerce")
            # Bỏ cột toàn NaN
            df_num = df_num.dropna(axis=1, how="all")
            if df_num.empty:
                continue

            # Đảm bảo index là DatetimeIndex
            if not isinstance(df_num.index, pd.DatetimeIndex):
                try:
                    df_num.index = pd.to_datetime(df_num.index)
                except Exception:
                    continue

            # Sắp xếp index + bỏ trùng
            df_num = df_num[~df_num.index.duplicated(keep="first")]
            df_num = df_num.sort_index()

            # Đổi tên cột
            df_r = df_num.copy()
            df_r.columns = [f"{mk}_{c}" for c in df_num.columns]
            all_members.append(df_r)
        except Exception as e:
            print(f"[MEDIAN] Bỏ qua {mk}: {e}")
            continue

    if not all_members:
        return pd.DataFrame()

    try:
        # Concatenate với outer join để align index
        combined = pd.concat(all_members, axis=1, join="outer")
        # Ép numeric lần cuối
        combined = combined.apply(pd.to_numeric, errors="coerce")
        combined = combined.sort_index()

        # Chỉ giữ dòng có ít nhất 1 giá trị
        combined = combined.dropna(how="all")
        if combined.empty:
            return pd.DataFrame()

        out = pd.DataFrame(index=combined.index)
        out["median"] = combined.median(axis=1).astype(float)
        out["mean"] = combined.mean(axis=1).astype(float)
        out["p10"] = combined.quantile(0.10, axis=1).astype(float)
        out["p25"] = combined.quantile(0.25, axis=1).astype(float)
        out["p75"] = combined.quantile(0.75, axis=1).astype(float)
        out["p90"] = combined.quantile(0.90, axis=1).astype(float)
        out["n_members"] = combined.notna().sum(axis=1).astype(int)

        # Bỏ dòng median NaN
        out = out.dropna(subset=["median"], how="all")
        return out
    except Exception as e:
        print(f"[MEDIAN] Lỗi tính toán: {e}")
        return pd.DataFrame()


# ============================================================
# XÁC SUẤT VƯỢT NGƯỠNG
# ============================================================
def probability_exceed(df: pd.DataFrame, threshold: float,
                       direction: str = "above") -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    try:
        df_num = df.apply(pd.to_numeric, errors="coerce")
        if direction == "above":
            prob = (df_num > threshold).sum(axis=1) / df_num.notna().sum(axis=1)
        else:
            prob = (df_num < threshold).sum(axis=1) / df_num.notna().sum(axis=1)
        return prob.replace([np.inf, -np.inf], np.nan)
    except Exception:
        return pd.Series(dtype=float)


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
        try:
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
        except Exception:
            pass

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
    try:
        return {
            "max_mean": float(stats["mean"].max()),
            "min_mean": float(stats["mean"].min()),
            "time_max": str(stats["mean"].idxmax()),
            "time_min": str(stats["mean"].idxmin()),
            "max_abs": float(stats["max"].max()),
            "min_abs": float(stats["min"].min()),
            "avg_std": float(stats["std"].mean()),
        }
    except Exception:
        return {}


def summarize_precipitation(stats: pd.DataFrame) -> Dict:
    if stats is None or stats.empty:
        return {}
    try:
        return {
            "total_rain_mm": float(stats["mean"].sum()),
            "total_rain_p90_mm": float(stats["p90"].sum()),
            "peak_hourly_mm": float(stats["mean"].max()),
            "time_peak": str(stats["mean"].idxmax()),
            "avg_std": float(stats["std"].mean()),
        }
    except Exception:
        return {}