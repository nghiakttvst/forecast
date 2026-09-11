"""
Module đọc GeoJSON Việt Nam — KHÔNG dùng shapely.
Tự động tải từ GitHub Releases.
Reverse geocoding = tắt (dùng forward geocoding + online).
"""

import json
import os
import pickle
import time
import unicodedata
import hashlib
import urllib.request
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from functools import lru_cache


# ============================================================
# ĐƯỜNG DẪN
# ============================================================
GEOJSON_DIR = Path(os.getenv("GEOJSON_DIR", Path(__file__).parent / "geojson"))
CACHE_DIR = Path(os.getenv("GEOJSON_CACHE_DIR", Path(__file__).parent / "data" / "geojson_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GEOJSON_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CẤU HÌNH URL — ĐÃ SỬA CHO REPO `forecast`
# ============================================================
GITHUB_RELEASE_BASE = os.getenv(
    "GITHUB_RELEASE_BASE",
    "https://github.com/nghiakttvst/forecast/releases/download/v1.0-geojson",
)

GEOJSON_URLS = {
    "vn_provinces.geojson": os.getenv(
        "GEOJSON_PROVINCES_URL",
        f"{GITHUB_RELEASE_BASE}/vn_provinces.geojson",
    ),
    "vn_Commune_Ward.geojson": os.getenv(
        "GEOJSON_COMMUNE_URL",
        f"{GITHUB_RELEASE_BASE}/vn_Commune_Ward.geojson",
    ),
}

DOWNLOAD_TIMEOUT = 600


PROVINCE_CANDIDATES = [
    "vn_provinces.geojson", "vn_province.geojson",
    "vn_provinces.json", "provinces.geojson",
]

COMMUNE_CANDIDATES = [
    "vn_Commune_Ward.geojson",
    "vn_Commune _Ward.geojson",
    "vn_commune_ward.geojson",
    "vn_communes.geojson",
]


def _find_file(candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = GEOJSON_DIR / name
        if p.exists() and p.stat().st_size > 1000:
            return p
    return None


def get_province_file() -> Optional[Path]:
    _ensure_geojson_downloaded()
    return _find_file(PROVINCE_CANDIDATES)


def get_commune_file() -> Optional[Path]:
    _ensure_geojson_downloaded()
    return _find_file(COMMUNE_CANDIDATES)


# ============================================================
# AUTO-DOWNLOAD
# ============================================================
_download_state = {"province": "pending", "commune": "pending"}


def _ensure_geojson_downloaded():
    if not _find_file(PROVINCE_CANDIDATES) and _download_state["province"] == "pending":
        _download_state["province"] = "trying"
        ok = _download_geojson("vn_provinces.geojson",
                               GEOJSON_URLS["vn_provinces.geojson"])
        _download_state["province"] = "done" if ok else "failed"

    if not _find_file(COMMUNE_CANDIDATES) and _download_state["commune"] == "pending":
        _download_state["commune"] = "trying"
        ok = _download_geojson("vn_Commune_Ward.geojson",
                               GEOJSON_URLS["vn_Commune_Ward.geojson"])
        _download_state["commune"] = "done" if ok else "failed"


def _download_geojson(filename: str, url: str, max_retries: int = 3) -> bool:
    target = GEOJSON_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[GEOJSON] ⬇️ Tải {filename} (lần {attempt}/{max_retries})")
            req = urllib.request.Request(
                url, headers={"User-Agent": "WeatherNext-App/1.0"}
            )
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                chunk_size = 1024 * 1024
                downloaded = 0
                with open(target, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
            print(f"[GEOJSON] ✅ Đã tải {filename}: {target.stat().st_size/1e6:.2f} MB")
            return True
        except Exception as e:
            print(f"[GEOJSON] ❌ Lỗi tải {filename}: {e}")
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
            if attempt < max_retries:
                time.sleep(3)
    return False


# ============================================================
# CHUỖI
# ============================================================
def strip_accents(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    if not text:
        return ""
    s = strip_accents(text.lower())
    for prefix in [
        "thanh pho ", "tp. ", "tp ", "tinh ", "quan ", "huyen ",
        "phuong ", "xa ", "thi tran ", "thi xa ",
        "p. ", "q. ", "tt. ", "tx. ",
    ]:
        if s.startswith(prefix):
            s = s[len(prefix):]
    return " ".join(s.split())


def _normalize_keep_prefix(text: str) -> str:
    if not text:
        return ""
    return " ".join(strip_accents(text.lower()).split())


# ============================================================
# CACHE
# ============================================================
def _file_hash(path: Path) -> str:
    stat = path.stat()
    key = f"{path.name}_{stat.st_size}_{int(stat.st_mtime)}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _cache_path(level: str, source: Path) -> Path:
    return CACHE_DIR / f"{level}_{_file_hash(source)}.pkl"


def _save_cache(level: str, source: Path, data: Any):
    try:
        cp = _cache_path(level, source)
        with open(cp, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        print(f"[GEOJSON] Cache lỗi: {e}")


def _load_cache(level: str, source: Path) -> Optional[Any]:
    cp = _cache_path(level, source)
    if not cp.exists():
        return None
    try:
        with open(cp, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def clear_cache():
    _get_index.cache_clear()
    try:
        for f in CACHE_DIR.glob("*.pkl"):
            f.unlink()
    except Exception:
        pass


# ============================================================
# TRÍCH XUẤT TÊN
# ============================================================
def _extract_names(props: Dict[str, Any], level: str = "province"):
    names: List[str] = []
    display: Optional[str] = None

    if level == "commune":
        ten_xa = None
        for f in ("ten_xa", "TenXa", "TEN_XA", "ten_phuong", "ten_xa_phuong"):
            v = props.get(f)
            if isinstance(v, str) and v.strip():
                ten_xa = v.strip()
                break
        if not ten_xa:
            for f in ("name", "Name", "ten", "Ten", "NAME_3", "NAME_2"):
                v = props.get(f)
                if isinstance(v, str) and v.strip():
                    ten_xa = v.strip()
                    break
        if not ten_xa:
            return [], None

        loai = str(props.get("loai") or props.get("Loai") or "").strip().lower()
        ten_tinh = str(props.get("ten_tinh") or props.get("TenTinh") or "").strip()

        tien_to = ""
        if loai in ("phường", "phuong"):
            tien_to = "Phường"
        elif loai in ("xã", "xa"):
            tien_to = "Xã"
        elif loai in ("thị trấn", "thi tran"):
            tien_to = "Thị trấn"
        elif loai in ("thị xã", "thi xa"):
            tien_to = "Thị xã"

        name_wp = f"{tien_to} {ten_xa}" if tien_to else ten_xa
        display = f"{name_wp}, {ten_tinh}" if ten_tinh else name_wp

        names.append(ten_xa)
        names.append(strip_accents(ten_xa))
        if tien_to:
            names.append(name_wp)
            names.append(f"{tien_to.lower()} {ten_xa}")
            names.append(strip_accents(f"{tien_to} {ten_xa}"))
        if ten_tinh:
            names.append(f"{ten_xa}, {ten_tinh}")
            names.append(f"{strip_accents(ten_xa)}, {strip_accents(ten_tinh)}")
            names.append(f"{name_wp}, {ten_tinh}")
    else:
        ten_tinh = None
        for f in ("ten_tinh", "TenTinh", "TEN_TINH", "name", "Name", "NAME",
                  "ten", "Ten", "province", "Province", "NAME_1"):
            v = props.get(f)
            if isinstance(v, str) and v.strip():
                ten_tinh = v.strip()
                break
        if not ten_tinh:
            for k, v in props.items():
                if isinstance(v, str) and v.strip() and len(v) > 2:
                    if k.lower() in ("ma_tinh", "code", "id", "gid_1"):
                        continue
                    if v.isdigit():
                        continue
                    ten_tinh = v.strip()
                    break
        if not ten_tinh:
            return [], None
        display = ten_tinh
        names.append(ten_tinh)
        names.append(strip_accents(ten_tinh))

    seen = set()
    unique = []
    for n in names:
        if not n:
            continue
        k = _normalize_keep_prefix(n)
        if k and k not in seen:
            seen.add(k)
            unique.append(n)
    return unique, display


# ============================================================
# BUILD INDEX (không dùng shapely)
# ============================================================
def _polygon_centroid(geom: dict):
    """Tính centroid thủ công từ GeoJSON coordinates."""
    try:
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])
        if gtype == "Polygon":
            ring = coords[0]
        elif gtype == "MultiPolygon":
            ring = coords[0][0]
        else:
            return None
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return (sum(lats) / len(lats), sum(lons) / len(lons))  # (lat, lon)
    except Exception:
        return None


def _build_index(path: Path, level: str) -> Dict[str, Any]:
    print(f"[GEOJSON] Build index {level}: {path.name}")
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)

    features = gj.get("features", [])
    if not features and gj.get("type") == "FeatureCollection":
        features = gj.get("features", [])
    elif not features and gj.get("type") == "Feature":
        features = [gj]

    index: Dict[str, Dict[str, Any]] = {}
    entries: List[Dict[str, Any]] = []

    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        centroid = _polygon_centroid(geom)
        if not centroid:
            continue

        names, display = _extract_names(props, level=level)
        if not names or not display:
            continue

        entry = {
            "display": display,
            "all_names": names,
            "centroid": centroid,
            "props": props,
        }
        entries.append(entry)

        for n in names:
            k1 = normalize(n)
            if k1 and k1 not in index:
                index[k1] = entry
            k2 = _normalize_keep_prefix(n)
            if k2 and k2 not in index:
                index[k2] = entry

    result = {"index": index, "entries": entries, "count": len(entries)}
    print(f"[GEOJSON] ✅ {level}: {len(entries)} polygon, {len(index)} key")
    return result


@lru_cache(maxsize=4)
def _get_index(level: str) -> Dict[str, Any]:
    if level == "province":
        path = get_province_file()
    elif level == "commune":
        path = get_commune_file()
    else:
        raise ValueError(f"level không hợp lệ: {level}")

    if not path:
        return {"index": {}, "entries": [], "count": 0}

    cached = _load_cache(level, path)
    if cached is not None:
        return cached

    result = _build_index(path, level)
    _save_cache(level, path, result)
    return result


# ============================================================
# FORWARD GEOCODING
# ============================================================
def forward_geocode(address: str, level: str = "province",
                    exact_only: bool = False) -> Optional[Tuple[float, float, str]]:
    if not address or not address.strip():
        return None

    data = _get_index(level)
    index = data.get("index", {})
    if not index:
        return None

    addr_clean = address.strip().rstrip(",")
    parts = [p.strip() for p in addr_clean.split(",") if p.strip()]

    for candidate in [addr_clean] + parts:
        for key_fn in (_normalize_keep_prefix, normalize):
            k = key_fn(candidate)
            if k in index:
                e = index[k]
                return e["centroid"][0], e["centroid"][1], e["display"]

    if exact_only:
        return None

    best = None
    best_len = 0
    for candidate in parts + [addr_clean]:
        c_kp = _normalize_keep_prefix(candidate)
        c_norm = normalize(candidate)
        if len(c_norm) < 3:
            continue
        for key, entry in index.items():
            if len(key) < 4:
                continue
            if (key in c_kp or c_kp in key or key in c_norm or c_norm in key):
                if len(key) > best_len:
                    best_len = len(key)
                    best = entry

    if best:
        return best["centroid"][0], best["centroid"][1], best["display"]
    return None


# ============================================================
# REVERSE GEOCODING — TẮT (không shapely)
# ============================================================
def reverse_geocode(lat: float, lon: float, level: str = "province") -> Optional[str]:
    return None


def reverse_geocode_full(lat: float, lon: float) -> Dict[str, Optional[str]]:
    return {"province": None, "commune": None}


# ============================================================
# LIỆT KÊ
# ============================================================
def list_provinces() -> List[str]:
    data = _get_index("province")
    seen = set()
    out = []
    for e in data.get("entries", []):
        if e["display"] not in seen:
            seen.add(e["display"])
            out.append(e["display"])
    return sorted(out)


def list_communes(province: Optional[str] = None) -> List[str]:
    data = _get_index("commune")
    seen = set()
    out = []
    p_norm = normalize(province) if province else None
    for e in data.get("entries", []):
        if e["display"] in seen:
            continue
        if p_norm:
            d_norm = normalize(e["display"])
            if p_norm not in d_norm:
                continue
        seen.add(e["display"])
        out.append(e["display"])
    return sorted(out)


def geojson_status() -> Dict[str, Any]:
    _ensure_geojson_downloaded()
    pf = get_province_file()
    cf = get_commune_file()
    return {
        "province_file": pf.name if pf else None,
        "commune_file": cf.name if cf else None,
        "province_exists": pf is not None,
        "commune_exists": cf is not None,
        "download_state": dict(_download_state),
    }