"""
Cấu hình chung — Đài KTTV TP. Cần Thơ
"""

from pathlib import Path

ENSEMBLE_API = "https://ensemble-api.open-meteo.com/v1/ensemble"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
GEOCODING_USER_AGENT = "kttv_cantho_app_v1 (contact@kttvcantho.gov.vn)"


# ============================================================
# MÔ HÌNH ENSEMBLE
# ============================================================
MODELS = {
    "weathernext2": {
        "label": "WeatherNext 2 (Google)",
        "api_name": "google_weathernext2_ensemble",
        "color": "#4285F4",
        "members": 64, "region": "Global", "resolution_km": 25,
        "ensemble": True, "update_freq_hours": 12, "update_cycles": [0, 12],
        "is_main": True,
    },
    "gfs_ensemble": {
        "label": "GFS Ensemble (NOAA)",
        "api_name": "gfs025",
        "color": "#34A853",
        "members": 31, "region": "Global", "resolution_km": 25,
        "ensemble": True, "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
        "is_main": True,
    },
    "ecmwf_ensemble": {
        "label": "ECMWF IFS Ensemble",
        "api_name": "ecmwf_ifs025",
        "color": "#EA4335",
        "members": 51, "region": "Global", "resolution_km": 25,
        "ensemble": True, "update_freq_hours": 12, "update_cycles": [0, 12],
        "is_main": True,
    },
    "icon_ensemble": {
        "label": "ICON Ensemble (DWD)",
        "api_name": "icon_seamless",
        "color": "#FBBC04",
        "members": 40, "region": "Global / Europe", "resolution_km": 11,
        "ensemble": True, "update_freq_hours": 6,
        "update_cycles": [0, 6, 12, 18],
        "is_main": True,
    },
    "gem_ensemble": {
        "label": "GEM Ensemble (Canada)",
        "api_name": "gem_global",
        "color": "#A142F4",
        "members": 21, "region": "Global / North America",
        "resolution_km": 15, "ensemble": True,
        "update_freq_hours": 12, "update_cycles": [0, 12],
        "is_main": True,
    },
}

DETERMINISTIC_MODELS = {
    "meteofrance_world": {
        "label": "Meteo-France ARPEGE",
        "api_name": "meteofrance_arpege_world",
        "color": "#00ACC1", "members": 1, "region": "Global",
        "resolution_km": 10, "ensemble": False,
        "update_freq_hours": 6, "update_cycles": [0, 6, 12, 18],
        "is_main": False,
    },
    "jma_global": {
        "label": "JMA GSM (Nhật)",
        "api_name": "jma_seamless",
        "color": "#F57C00", "members": 1, "region": "Global",
        "resolution_km": 55, "ensemble": False,
        "update_freq_hours": 6, "update_cycles": [0, 6, 12, 18],
        "is_main": False,
    },
    "ukmo_global": {
        "label": "UKMO Global",
        "api_name": "ukmo_seamless",
        "color": "#C62828", "members": 1, "region": "Global",
        "resolution_km": 10, "ensemble": False,
        "update_freq_hours": 6, "update_cycles": [0, 6, 12, 18],
        "is_main": False,
    },
}

MAIN_MODELS = [k for k, v in MODELS.items() if v.get("is_main")]


# ============================================================
# BIẾN
# ============================================================
DEFAULT_VARIABLES = ["temperature_2m", "precipitation"]
VARIABLE_INFO = {
    "temperature_2m": {"label": "Nhiệt độ 2m", "unit": "°C"},
    "precipitation": {"label": "Mưa 1h", "unit": "mm"},
}


# ============================================================
# QCVN 84:2024/BTNMT
# ============================================================
QCVN_PRECIP_THRESHOLDS = {
    "0-12h":  {"lower": -0.20, "upper": 0.20},
    "12-24h": {"lower": -0.30, "upper": 0.30},
    "24-48h": {"lower": -0.40, "upper": 0.40},
    "48h+":   {"lower": -0.50, "upper": 0.50},
}
QCVN_TEMP_THRESHOLDS = {
    "0-24h": 2.0, "24-48h": 2.5, "48-72h": 3.0, "72h+": 3.5,
}


# ============================================================
# QCVN 46:2012/BTNMT + WMO — Phân loại mưa
# ============================================================
RAIN_THRESHOLDS_1H = {
    "trace":       0.1,
    "small":       2.5,
    "moderate":    7.5,
    "heavy":      15.0,
    "very_heavy": 30.0,
}

RAIN_THRESHOLDS_24H = {
    "small":        5.0,
    "moderate":    25.0,
    "heavy":       50.0,
    "very_heavy": 100.0,
}

RAIN_THRESHOLDS = {
    "rain_trace": RAIN_THRESHOLDS_1H["trace"],
    "rain_light": RAIN_THRESHOLDS_1H["small"],
    "rain_moderate": RAIN_THRESHOLDS_1H["moderate"],
    "rain_heavy": RAIN_THRESHOLDS_1H["heavy"],
    "rain_very_heavy": RAIN_THRESHOLDS_1H["very_heavy"],
}


# ============================================================
# CẢNH BÁO CỰC ĐOAN
# ============================================================
ALERT_THRESHOLDS = {
    "temp_high": 35.0, "temp_low": 10.0,
    "rain_heavy_1h": 20.0, "rain_heavy_24h": 50.0,
    "wind_high": 15.0,
}
ALERT_PROB_THRESHOLD = 0.30


# ============================================================
# LƯU TRỮ
# ============================================================
DB_PATH = str(Path(__file__).parent / "data" / "history.db")


# ============================================================
# BẢN TIN
# ============================================================
BULLETIN_CATEGORIES = {
    "daily":       {"label": "Bản tin dự báo hàng ngày", "icon": "📰"},
    "rain_storm":  {"label": "Bản tin dự báo mưa dông",  "icon": "⛈️"},
    "heavy_rain":  {"label": "Bản tin mưa lớn",          "icon": "🌧️"},
    "hydro":       {"label": "Bản tin thủy văn",         "icon": "🌊"},
}

BULLETIN_MAX_SIZE_MB = 10


# ============================================================
# THÔNG BÁO
# ============================================================
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""
SMTP_PASSWORD = ""