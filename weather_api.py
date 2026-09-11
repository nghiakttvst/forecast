"""
Module lấy dữ liệu dự báo từ Open-Meteo Ensemble API.
Hỗ trợ nhiều mô hình: WeatherNext 2, GFS, ECMWF, ICON, GEM.
"""

import time
import unicodedata
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple

from config import ENSEMBLE_API, MODELS, GEOCODING_USER_AGENT
from geojson_lookup import (
    forward_geocode as geojson_forward,
    reverse_geocode as geojson_reverse,
    reverse_geocode_full as geojson_reverse_full,
    geojson_status,
    clear_cache as geojson_clear_cache,
)

try:
    from vn_locations import lookup_vn_location
    _HAS_VN_LOCATIONS = True
except ImportError:
    _HAS_VN_LOCATIONS = False
    def lookup_vn_location(address):
        return None

TIMEOUT = 60


# ============================================================
# GEOCODING
# ============================================================
def geocode_address(address: str) -> Optional[Tuple[float, float, str]]:
    if not address or not address.strip():
        return None
    address = address.strip()
    print(f"\n[GEO] Xử lý: '{address}'")

    addr_lower = address.lower()
    has_comma = "," in address
    has_commune_kw = any(k in addr_lower for k in [
        "phường", "phuong", "xã", "xa ", "commune", "ward",
        "p.", "tt.", "thị trấn", "thi tran",
    ])

    if not has_comma and not has_commune_kw:
        try:
            r = geojson_forward(address, level="province", exact_only=True)
            if r:
                print(f"[GEO] ✅ Tỉnh (exact): {r[2]} → ({r[0]:.4f}, {r[1]:.4f})")
                return r
        except Exception as e:
            print(f"[GEO] Lỗi tỉnh exact: {e}")

    try:
        r = geojson_forward(address, level="commune")
        if r:
            print(f"[GEO] ✅ Xã/Phường: {r[2]} → ({r[0]:.4f}, {r[1]:.4f})")
            return r
    except FileNotFoundError:
        print("[GEO] Chưa có file GeoJSON phường/xã.")
    except Exception as e:
        print(f"[GEO] Lỗi GeoJSON phường/xã: {e}")

    try:
        r = geojson_forward(address, level="province")
        if r:
            print(f"[GEO] ✅ Tỉnh (full): {r[2]} → ({r[0]:.4f}, {r[1]:.4f})")
            return r
    except Exception as e:
        print(f"[GEO] Lỗi GeoJSON tỉnh: {e}")

    if _HAS_VN_LOCATIONS:
        r = lookup_vn_location(address)
        if r:
            print(f"[GEO] ✅ DB nội bộ: {r[2]}")
            return r

    print("[GEO] Thử Photon…")
    r = _try_photon(address)
    if r:
        return r

    print("[GEO] Thử Nominatim…")
    r = _try_nominatim(address)
    if r:
        return r

    print("[GEO] ❌ Không tìm thấy.")
    return None


def _try_photon(address: str) -> Optional[Tuple[float, float, str]]:
    url = "https://photon.komoot.io/api/"
    for q in _variants(address):
        try:
            r = requests.get(url, params={"q": q, "limit": 1}, timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            feats = data.get("features", [])
            if feats:
                f = feats[0]
                lon, lat = f["geometry"]["coordinates"]
                p = f["properties"]
                name = ", ".join(filter(None, [
                    p.get("name"), p.get("city"),
                    p.get("state"), p.get("country"),
                ])) or q
                return float(lat), float(lon), name
        except Exception as e:
            print(f"[PHOTON] Lỗi: {e}")
            return None
        time.sleep(0.3)
    return None


def _try_nominatim(address: str) -> Optional[Tuple[float, float, str]]:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": GEOCODING_USER_AGENT}
    for q in _variants(address):
        try:
            r = requests.get(
                url, params={"q": q, "format": "json", "limit": 1},
                headers=headers, timeout=10,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", q)
        except Exception as e:
            print(f"[NOMINATIM] Lỗi: {e}")
            return None
        time.sleep(1.2)
    return None


def _variants(address: str) -> List[str]:
    def strip(s: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFKD", s)
            if not unicodedata.combining(c)
        )
    a = address.strip()
    return list(dict.fromkeys([a, strip(a), f"{a}, Vietnam", f"{strip(a)}, Vietnam"]))


def reverse_geocode_location(lat: float, lon: float) -> Dict[str, Optional[str]]:
    return geojson_reverse_full(lat, lon)


def get_geojson_status() -> Dict:
    return geojson_status()


def reload_geojson():
    geojson_clear_cache()


# ============================================================
# GỌI API
# ============================================================
def fetch_model_ensemble(lat: float, lon: float, model_key: str,
                         variables: List[str] = None, days: int = 15) -> Dict:
    if variables is None:
        variables = ["temperature_2m", "precipitation"]

    model_info = MODELS.get(model_key)
    if not model_info:
        raise ValueError(f"Mô hình không hỗ trợ: {model_key}")

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(variables),
        "forecast_days": days,
        "models": model_info["api_name"],
        "timezone": "auto",
    }

    print(f"[API] {model_info['label']} – ({lat:.4f}, {lon:.4f})")
    resp = requests.get(ENSEMBLE_API, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(
            f"{model_info['label']} lỗi: {data['error']} — {data.get('reason', '')}"
        )
    return data


def fetch_all_models(lat: float, lon: float, variables: List[str] = None,
                     days: int = 15, model_keys: List[str] = None) -> Dict[str, Dict]:
    if model_keys is None:
        model_keys = list(MODELS.keys())

    results = {}
    for key in model_keys:
        try:
            results[key] = fetch_model_ensemble(lat, lon, key, variables, days)
        except Exception as e:
            print(f"[WARN] Bỏ qua {key}: {e}")
    return results


# ============================================================
# PARSE ENSEMBLE
# ============================================================
def parse_ensemble(data: Dict, variable: str) -> pd.DataFrame:
    hourly = data.get("hourly", {})
    if "time" not in hourly:
        return pd.DataFrame()

    times = pd.to_datetime(hourly["time"])
    member_keys = [
        k for k in hourly.keys()
        if k == variable or k.startswith(f"{variable}_member")
    ]
    if not member_keys:
        return pd.DataFrame()

    df = pd.DataFrame(index=times)
    for key in sorted(member_keys):
        col = "control" if key == variable else key.replace(f"{variable}_", "")
        df[col] = hourly[key]

    df.index.name = "time"
    return df


def build_ensemble_dict(raw_models: Dict[str, Dict], variable: str) -> Dict[str, pd.DataFrame]:
    out = {}
    for key, raw in raw_models.items():
        df = parse_ensemble(raw, variable)
        if not df.empty:
            out[key] = df
    return out


def get_model_info(model_key: str) -> Dict:
    return MODELS.get(model_key, {})