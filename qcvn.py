"""
Module đánh giá chất lượng dự báo theo QCVN 84:2024/BTNMT.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from config import QCVN_PRECIP_THRESHOLDS, QCVN_TEMP_THRESHOLDS


def mean_error(forecast: np.ndarray, observed: np.ndarray) -> float:
    mask = ~(np.isnan(forecast) | np.isnan(observed))
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(forecast[mask] - observed[mask]))


def mean_absolute_error(forecast: np.ndarray, observed: np.ndarray) -> float:
    mask = ~(np.isnan(forecast) | np.isnan(observed))
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs(forecast[mask] - observed[mask])))


def root_mean_square_error(forecast: np.ndarray, observed: np.ndarray) -> float:
    mask = ~(np.isnan(forecast) | np.isnan(observed))
    if mask.sum() == 0:
        return np.nan
    return float(np.sqrt(np.mean((forecast[mask] - observed[mask]) ** 2)))


def bias_score(forecast: np.ndarray, observed: np.ndarray) -> float:
    mask = ~(np.isnan(forecast) | np.isnan(observed))
    if mask.sum() == 0:
        return np.nan
    obs_mean = np.mean(observed[mask])
    if obs_mean == 0:
        return np.nan
    return float(np.mean(forecast[mask]) / obs_mean)


def probability_of_correct(forecast: np.ndarray, observed: np.ndarray,
                            tolerance: float = 2.0) -> float:
    mask = ~(np.isnan(forecast) | np.isnan(observed))
    if mask.sum() == 0:
        return np.nan
    correct = np.sum(np.abs(forecast[mask] - observed[mask]) <= tolerance)
    return float(correct / mask.sum())


def compute_scf(series: np.ndarray) -> float:
    mask = ~np.isnan(series)
    if mask.sum() < 2:
        return np.nan
    sigma = np.std(series[mask], ddof=1)
    return float(1.5 * sigma)


def get_qcvn_threshold_precip(hour_offset: int) -> Tuple[float, float]:
    if hour_offset <= 12:
        t = QCVN_PRECIP_THRESHOLDS["0-12h"]
    elif hour_offset <= 24:
        t = QCVN_PRECIP_THRESHOLDS["12-24h"]
    elif hour_offset <= 48:
        t = QCVN_PRECIP_THRESHOLDS["24-48h"]
    else:
        t = QCVN_PRECIP_THRESHOLDS["48h+"]
    return t["lower"], t["upper"]


def get_qcvn_threshold_temp(hour_offset: int) -> float:
    if hour_offset <= 24:
        return QCVN_TEMP_THRESHOLDS["0-24h"]
    elif hour_offset <= 48:
        return QCVN_TEMP_THRESHOLDS["24-48h"]
    elif hour_offset <= 72:
        return QCVN_TEMP_THRESHOLDS["48-72h"]
    else:
        return QCVN_TEMP_THRESHOLDS["72h+"]


def evaluate_forecast_qcvn(forecast_df: pd.DataFrame, observed_df: pd.DataFrame,
                            variable: str, variable_type: str) -> pd.DataFrame:
    forecast_mean = forecast_df.mean(axis=1)
    common_idx = forecast_mean.index.intersection(observed_df.index)
    if len(common_idx) == 0:
        return pd.DataFrame()

    f = forecast_mean.loc[common_idx].values
    o = observed_df.loc[common_idx, "observed"].values
    hours = np.arange(len(f))

    results = []
    for h in hours:
        if np.isnan(f[h]) or np.isnan(o[h]):
            continue

        me = f[h] - o[h]
        mae = abs(me)
        mse = me ** 2
        bias = f[h] / o[h] if o[h] != 0 else np.nan

        if variable_type == "precipitation":
            lo_pct, hi_pct = get_qcvn_threshold_precip(int(h))
            scf_lower = o[h] * (1 + lo_pct)
            scf_upper = o[h] * (1 + hi_pct)
            scf = (scf_upper - scf_lower) / 2
            is_within = scf_lower <= f[h] <= scf_upper
        else:
            scf = get_qcvn_threshold_temp(int(h))
            is_within = abs(me) <= scf

        results.append({
            "hour": int(h), "forecast": f[h], "observed": o[h],
            "ME": me, "MAE": mae, "MSE": mse, "Bias": bias,
            "Scf": scf, "within_qcvn": is_within,
            "PC": 1.0 if is_within else 0.0,
        })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    df["RMSE_cum"] = np.sqrt(df["MSE"].expanding().mean())
    return df


def summarize_qcvn_evaluation(eval_df: pd.DataFrame) -> Dict:
    if eval_df.empty:
        return {}
    return {
        "ME": float(eval_df["ME"].mean()),
        "MAE": float(eval_df["MAE"].mean()),
        "RMSE": float(np.sqrt(eval_df["MSE"].mean())),
        "Bias": float(eval_df["Bias"].mean(skipna=True)),
        "PC": float(eval_df["PC"].mean()),
        "Scf_mean": float(eval_df["Scf"].mean()),
        "n_points": len(eval_df),
        "pct_within_qcvn": float(eval_df["within_qcvn"].mean() * 100),
    }


def grade_forecast_qcvn(summary: Dict) -> str:
    pct = summary.get("pct_within_qcvn", 0)
    if pct >= 90:
        return "🟢 Tốt (đạt QCVN)"
    elif pct >= 75:
        return "🟡 Khá (gần đạt QCVN)"
    elif pct >= 60:
        return "🟠 Trung bình (chưa đạt QCVN)"
    else:
        return "🔴 Kém (không đạt QCVN)"