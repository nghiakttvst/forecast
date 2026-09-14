"""
Cấu hình chung cho ứng dụng WeatherNext.
"""

from pathlib import Path

# ============================================================
# API ENDPOINTS
# ============================================================
ENSEMBLE_API = "https://ensemble-api.open-meteo.com/v1/ensemble"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
GEOCODING_USER_AGENT = "weathernext_app_v1 (contact@example.com)"


# ============================================================
# MÔ HÌNH ENSEMBLE (nhiều thành viên)
# ============================================================
MODELS = {
    "weathernext2": {
        "label": "WeatherNext 2 (Google)",
        "api_name": "google_weathernext2_ensemble",
        "color": "#4285F4",
        "members": 64,
        "region": "Global",
        "resolution_km": 25,
        "ensemble": True,
        "update_freq_hours": 12,
        "update_cycles": [0, 12],
    },
    "gfs_ensemble": {
        "label": "GFS Ensemble (NOAA)",
        "api_name": "gfs025",
        "color": "#34A853",
        "members": 31,
        "region": "Global",
        "resolution_km": 25,
        "ensemble": True,
        "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
    },
    "ecmwf_ensemble": {
        "label": "ECMWF IFS Ensemble",
        "api_name": "ecmwf_ifs025",
        "color": "#EA4335",
        "members": 51,
        "region": "Global",
        "resolution_km": 25,
        "ensemble": True,
        "update_freq_hours": 12,
        "update_cycles": [0, 12],
    },
    "icon_ensemble": {
        "label": "ICON Ensemble (DWD)",
        "api_name": "icon_seamless",
        "color": "#FBBC04",
        "members": 40,
        "region": "Global / Europe",
        "resolution_km": 11,
        "ensemble": True,
        "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
    },
    "gem_ensemble": {
        "label": "GEM Ensemble (Canada)",
        "api_name": "gem_global",
        "color": "#A142F4",
        "members": 21,
        "region": "Global / North America",
        "resolution_km": 15,
        "ensemble": True,
        "update_freq_hours": 12,
        "update_cycles": [0, 12],
    },
}


# ============================================================
# MÔ HÌNH DETERMINISTIC (1 thành viên)
# ============================================================
DETERMINISTIC_MODELS = {
    "meteofrance_world": {
        "label": "Meteo-France ARPEGE (World)",
        "api_name": "meteofrance_arpege_world",
        "color": "#00ACC1",
        "members": 1,
        "region": "Global",
        "resolution_km": 10,
        "ensemble": False,
        "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
    },
    "jma_global": {
        "label": "JMA GSM (Nhat)",
        "api_name": "jma_seamless",
        "color": "#F57C00",
        "members": 1,
        "region": "Global / Japan",
        "resolution_km": 55,
        "ensemble": False,
        "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
    },
    "ukmo_global": {
        "label": "UKMO Global (UK Met Office)",
        "api_name": "ukmo_seamless",
        "color": "#C62828",
        "members": 1,
        "region": "Global / UK",
        "resolution_km": 10,
        "ensemble": False,
        "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
    },
}


# ============================================================
# BIẾN KHÍ TƯỢNG
# ============================================================
DEFAULT_VARIABLES = ["temperature_2m", "precipitation"]

VARIABLE_INFO = {
    "temperature_2m": {"label": "Nhiệt độ 2m", "unit": "°C", "type": "temperature"},
    "precipitation": {"label": "Mưa 1h", "unit": "mm", "type": "precipitation"},
}


# ============================================================
# QCVN 84:2024/BTNMT — Ngưỡng sai số cho phép
# ============================================================
QCVN_PRECIP_THRESHOLDS = {
    "0-12h": {"lower": -0.20, "upper": 0.20},
    "12-24h": {"lower": -0.30, "upper": 0.30},
    "24-48h": {"lower": -0.40, "upper": 0.40},
    "48h+": {"lower": -0.50, "upper": 0.50},
}

QCVN_TEMP_THRESHOLDS = {
    "0-24h": 2.0,
    "24-48h": 2.5,
    "48-72h": 3.0,
    "72h+": 3.5,
}


# ============================================================
# NGƯỠNG PHÂN LOẠI HIỆN TƯỢNG MƯA (QCVN 46:2012/BTNMT & WMO)
# ============================================================
RAIN_THRESHOLDS = {
    "rain_trace": 0.1,
    "rain_light": 2.5,
    "rain_moderate": 7.5,
    "rain_heavy": 15.0,
    "rain_very_heavy": 30.0,
}


# ============================================================
# CẢNH BÁO CỰC ĐOAN
# ============================================================
ALERT_THRESHOLDS = {
    "temp_high": 35.0,
    "temp_low": 10.0,
    "rain_heavy_1h": 20.0,
    "rain_heavy_24h": 50.0,
    "wind_high": 15.0,
}
ALERT_PROB_THRESHOLD = 0.30


# ============================================================
# LƯU TRỮ — ưu tiên Supabase, fallback SQLite local
# ============================================================
DB_PATH = str(Path(__file__).parent / "data" / "history.db")


# ============================================================
# THÔNG BÁO (tùy chọn)
# ============================================================
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""
SMTP_PASSWORD = ""