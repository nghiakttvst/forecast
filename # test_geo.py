# test_geo.py
import requests, json

TESTS = [
    "Ninh Kieu, Can Tho",
    "Ninh Kiều, Cần Thơ",
    "Can Tho",
    "Cần Thơ",
    "Hanoi",
    "Hà Nội",
]

print("=" * 60)
print("TEST 1: Nominatim trực tiếp qua requests")
print("=" * 60)

for q in TESTS:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "weathernext_app_v1 (test@example.com)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()
        if data:
            print(f"✅ '{q}' → ({data[0]['lat']}, {data[0]['lon']})")
            print(f"   Full: {data[0]['display_name']}")
        else:
            print(f"❌ '{q}' → không có kết quả")
    except Exception as e:
        print(f"💥 '{q}' → lỗi: {e}")

print("\n" + "=" * 60)
print("TEST 2: Photon (Komoot) – dịch vụ dự phòng")
print("=" * 60)

for q in TESTS:
    url = "https://photon.komoot.io/api/"
    params = {"q": q, "limit": 1}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("features"):
            f = data["features"][0]
            lon, lat = f["geometry"]["coordinates"]
            print(f"✅ '{q}' → ({lat}, {lon})")
            print(f"   Name: {f['properties'].get('name')}")
        else:
            print(f"❌ '{q}' → không có kết quả")
    except Exception as e:
        print(f"💥 '{q}' → lỗi: {e}")