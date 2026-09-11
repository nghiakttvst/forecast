"""Test geocoding sau khi sửa."""
from geojson_lookup import (
    get_commune_file, _load_file, _extract_names,
    forward_geocode, _get_index,
)

print("=" * 65)
print("CẤU TRÚC PROPERTIES (feature đầu file commune)")
print("=" * 65)
path = get_commune_file()
if path:
    gj = _load_file(str(path))
    feat0 = gj["features"][0]
    for k, v in feat0["properties"].items():
        print(f"  {k}: {v!r}")
    names, display = _extract_names(feat0["properties"], level="commune")
    print(f"\n  → Aliases: {names}")
    print(f"  → Display: {display!r}")

print("\n" + "=" * 65)
print("INDEX COMMUNE")
print("=" * 65)
idx = _get_index("commune")
print(f"Tổng số key: {len(idx)}")
print("\n10 key đầu:")
for k in list(idx.keys())[:10]:
    print(f"  {k!r} → {idx[k]['display']!r}")

print("\n" + "=" * 65)
print("TEST FORWARD – COMMUNE")
print("=" * 65)
for q in [
    "Ninh Kiều", "ninh kieu", "Phường Ninh Kiều",
    "Ba Đình", "Phường Ba Đình", "An Khánh", "Xã An Khánh",
    "Ninh Kiều, Cần Thơ", "Xuân Khánh",
]:
    r = forward_geocode(q, level="commune")
    if r:
        print(f"  ✅ '{q}' → ({r[0]:.4f}, {r[1]:.4f}) [{r[2]}]")
    else:
        print(f"  ❌ '{q}' → không tìm thấy")

print("\n" + "=" * 65)
print("TEST FORWARD – PROVINCE")
print("=" * 65)
for q in ["Cần Thơ", "Hà Nội", "Đà Nẵng", "TP. Hồ Chí Minh"]:
    r = forward_geocode(q, level="province")
    if r:
        print(f"  ✅ '{q}' → ({r[0]:.4f}, {r[1]:.4f}) [{r[2]}]")
    else:
        print(f"  ❌ '{q}' → không tìm thấy")