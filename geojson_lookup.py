"""
Module đọc GeoJSON Việt Nam (2 cấp: tỉnh/thành + phường/xã).
Tối ưu: Cache pickle + STRtree spatial index.
"""

import json
import pickle
import unicodedata
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from functools import lru_cache

from shapely.geometry import shape, Point
from shapely.strtree import STRtree

# ============================================================
# ĐƯỜNG DẪN
# ============================================================
GEOJSON_DIR = Path(__file__).parent / "geojson"
CACHE_DIR = Path(__file__).parent / "data" / "geojson_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROVINCE_CANDIDATES = [
    "vn_provinces.geojson", "vn_province.geojson",
    "vn_provinces.json", "provinces.geojson",
    "tinh_thanh.geojson",
]

COMMUNE_CANDIDATES = [
    "vn_Commune_Ward.geojson",
    "vn_Commune _Ward.geojson",
    "vn_commune_ward.geojson",
    "vn_communes.geojson",
    "vn_wards.geojson",
    "phuong_xa.geojson",
]


def _find_file(candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = GEOJSON_DIR / name
        if p.exists():
            return p
    return None


def get_province_file() -> Optional[Path]:
    return _find_file(PROVINCE_CANDIDATES)


def get_commune_file() -> Optional[Path]:
    return _find_file(COMMUNE_CANDIDATES)


# ============================================================
# TIỆN ÍCH CHUỖI
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
        "thanh pho ", "tp. ", "tp ", "tinh ",
        "quan ", "huyen ",
        "phuong ", "xa ", "thi tran ", "thi xa ",
        "p. ", "q. ", "tt. ", "tx. ",
    ]:
        if s.startswith(prefix):
            s = s[len(prefix):]
    return " ".join(s.split())


def _normalize_keep_prefix(text: str) -> str:
    if not text:
        return ""
    s = strip_accents(text.lower())
    return " ".join(s.split())


# ============================================================
# CACHE PICKLE
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
        print(f"[GEOJSON] Đã cache {level}: {cp.name}")
    except Exception as e:
        print(f"[GEOJSON] Không lưu được cache: {e}")


def _load_cache(level: str, source: Path) -> Optional[Any]:
    cp = _cache_path(level, source)
    if not cp.exists():
        return None
    try:
        with open(cp, "rb") as f:
            data = pickle.load(f)
        print(f"[GEOJSON] Đã nạp từ cache: {cp.name}")
        return data
    except Exception as e:
        print(f"[GEOJSON] Cache lỗi, bỏ qua: {e}")
        return None


def clear_cache():
    _get_index.cache_clear()
    try:
        for f in CACHE_DIR.glob("*.pkl"):
            f.unlink()
        print("[GEOJSON] Đã xóa cache file")
    except Exception as e:
        print(f"[GEOJSON] Lỗi xóa cache: {e}")


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

        name_with_prefix = f"{tien_to} {ten_xa}" if tien_to else ten_xa
        display = f"{name_with_prefix}, {ten_tinh}" if ten_tinh else name_with_prefix

        names.append(ten_xa)
        names.append(strip_accents(ten_xa))
        if tien_to:
            names.append(name_with_prefix)
            names.append(f"{tien_to.lower()} {ten_xa}")
            names.append(strip_accents(f"{tien_to} {ten_xa}"))
        if ten_tinh:
            names.append(f"{ten_xa}, {ten_tinh}")
            names.append(f"{strip_accents(ten_xa)}, {strip_accents(ten_tinh)}")
            names.append(f"{name_with_prefix}, {ten_tinh}")
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
# BUILD INDEX
# ============================================================
def _build_index(path: Path, level: str) -> Dict[str, Any]:
    print(f"[GEOJSON] Đang build index {level} từ {path.name}…")
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)

    features = gj.get("features", [])
    if not features and gj.get("type") == "FeatureCollection":
        features = gj.get("features", [])
    elif not features and gj.get("type") == "Feature":
        features = [gj]

    index: Dict[str, Dict[str, Any]] = {}
    entries: List[Dict[str, Any]] = []
    geometries: List[Any] = []

    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            shp = shape(geom)
            if not shp.is_valid:
                shp = shp.buffer(0)
            centroid = shp.centroid
        except Exception:
            continue

        names, display = _extract_names(props, level=level)
        if not names or not display:
            continue

        entry = {
            "display": display,
            "all_names": names,
            "centroid": (centroid.y, centroid.x),
            "bbox": shp.bounds,
            "props": props,
            "geom_idx": len(geometries),
        }
        entries.append(entry)
        geometries.append(shp)

        for n in names:
            k1 = normalize(n)
            if k1 and k1 not in index:
                index[k1] = entry
            k2 = _normalize_keep_prefix(n)
            if k2 and k2 not in index:
                index[k2] = entry

    try:
        tree = STRtree(geometries)
    except Exception as e:
        print(f"[GEOJSON] STRtree lỗi: {e}")
        tree = None

    result = {
        "index": index,
        "entries": entries,
        "geometries": geometries,
        "tree": tree,
        "count": len(entries),
    }
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
        return {"index": {}, "entries": [], "geometries": [], "tree": None, "count": 0}

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
# REVERSE GEOCODING
# ============================================================
def reverse_geocode(lat: float, lon: float, level: str = "province") -> Optional[str]:
    data = _get_index(level)
    tree = data.get("tree")
    entries = data.get("entries", [])
    geometries = data.get("geometries", [])

    if not entries or tree is None:
        return None

    pt = Point(lon, lat)
    try:
        idxs = tree.query(pt)
    except Exception:
        idxs = []

    for i in idxs:
        try:
            if geometries[i].contains(pt) or geometries[i].intersects(pt):
                return entries[i]["display"]
        except Exception:
            continue

    if not idxs:
        for entry in entries:
            try:
                if geometries[entry["geom_idx"]].contains(pt):
                    return entry["display"]
            except Exception:
                continue
    return None


def reverse_geocode_full(lat: float, lon: float) -> Dict[str, Optional[str]]:
    return {
        "province": reverse_geocode(lat, lon, level="province"),
        "commune": reverse_geocode(lat, lon, level="commune"),
    }


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


# ============================================================
# TRẠNG THÁI
# ============================================================
def geojson_status() -> Dict[str, Any]:
    pf = get_province_file()
    cf = get_commune_file()
    status = {
        "geojson_dir": str(GEOJSON_DIR),
        "cache_dir": str(CACHE_DIR),
        "province_file": pf.name if pf else None,
        "commune_file": cf.name if cf else None,
        "province_exists": pf is not None,
        "commune_exists": cf is not None,
    }
    if pf:
        status["province_size_mb"] = round(pf.stat().st_size / 1e6, 2)
        status["province_cached"] = _cache_path("province", pf).exists()
        try:
            data = _get_index("province")
            status["province_count"] = data.get("count", 0)
        except Exception as e:
            status["province_error"] = str(e)
    if cf:
        status["commune_size_mb"] = round(cf.stat().st_size / 1e6, 2)
        status["commune_cached"] = _cache_path("commune", cf).exists()
        try:
            data = _get_index("commune")
            status["commune_count"] = data.get("count", 0)
        except Exception as e:
            status["commune_error"] = str(e)
    return status