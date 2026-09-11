"""
Cấu hình chung cho ứng dụng WeatherNext.
"""

# ============================================================
# API ENDPOINTS
# ============================================================
ENSEMBLE_API = "https://ensemble-api.open-meteo.com/v1/ensemble"
GEOCODING_USER_AGENT = "weathernext_app_v1 (contact@example.com)"

# ============================================================
# CÁC MÔ HÌNH ENSEMBLE HỖ TRỢ
# ============================================================
MODELS = {
    "weathernext2": {
        "label": "WeatherNext 2 (Google)",
        "api_name": "google_weathernext2_ensemble",
        "color": "#4285F4",
        "members": 64,
        "region": "Global",
        "resolution_km": 25,
    },
    "gfs_ensemble": {
        "label": "GFS Ensemble (NOAA)",
        "api_name": "gfs025",
        "color": "#34A853",
        "members": 31,
        "region": "Global",
        "resolution_km": 25,
    },
    "ecmwf_ensemble": {
        "label": "ECMWF IFS Ensemble",
        "api_name": "ecmwf_ifs025",
        "color": "#EA4335",
        "members": 51,
        "region": "Global",
        "resolution_km": 25,
    },
    "icon_ensemble": {
        "label": "ICON Ensemble (DWD)",
        "api_name": "icon_seamless",
        "color": "#FBBC04",
        "members": 40,
        "region": "Global",
        "resolution_km": 26,
    },
}

# ============================================================
# BIẾN KHÍ TƯỢNG
# ============================================================
DEFAULT_VARIABLES = ["temperature_2m", "precipitation"]

VARIABLE_INFO = {
    "temperature_2m": {
        "label": "Nhiệt độ 2m",
        "unit": "°C",
        "type": "temperature",
    },
    "precipitation": {
        "label": "Mưa 1h",
        "unit": "mm",
        "type": "precipitation",
    },
}

# ============================================================
# QCVN 84:2024/BTNMT – NGƯỠNG SAI SỐ CHO PHÉP
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
# LƯU TRỮ
# ============================================================
DB_PATH = "data/history.db"

# ============================================================
# THÔNG BÁO (tùy chọn)
# ============================================================
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""
SMTP_PASSWORD = ""