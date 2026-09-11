"""Test từng mô hình xem có hoạt động không."""
import requests
from config import MODELS, ENSEMBLE_API

LAT, LON = 10.0291, 105.7706  # Cần Thơ

print("=" * 75)
print(f"TEST MODELS – Tọa độ ({LAT}, {LON})")
print("=" * 75)

for key, info in MODELS.items():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "temperature_2m",
        "forecast_days": 3,
        "models": info["api_name"],
        "timezone": "auto",
    }
    try:
        r = requests.get(ENSEMBLE_API, params=params, timeout=20)
        data = r.json()
        if "error" in data:
            print(f"❌ {info['label']:35s} | {data['error']}: {data.get('reason', '')}")
        elif "hourly" in data and "temperature_2m" in data["hourly"]:
            # Đếm số thành viên ensemble
            members = sum(
                1 for k in data["hourly"]
                if k == "temperature_2m" or k.startswith("temperature_2m_member")
            )
            print(f"✅ {info['label']:35s} | {members} thành viên")
        else:
            print(f"⚠️ {info['label']:35s} | Có phản hồi nhưng thiếu dữ liệu")
    except Exception as e:
        print(f"💥 {info['label']:35s} | Lỗi: {e}")