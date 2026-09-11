"""Build cache GeoJSON trước khi chạy app."""
import time
from geojson_lookup import _get_index

t0 = time.time()
data = _get_index('province')
print(f"Province: {data['count']} polygon, {time.time() - t0:.2f}s")

t0 = time.time()
data = _get_index('commune')
print(f"Commune: {data['count']} polygon, {time.time() - t0:.2f}s")

print("Xong! Cache đã sẵn sàng.")