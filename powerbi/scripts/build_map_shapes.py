"""Chuyển shapefile Taxi Zones thành TopoJSON (Shape map) và CSV tâm khu vực cho Power BI.

Chạy trong container Mage (cần extension spatial của DuckDB, tự cài ở lần chạy đầu, cần internet):
  docker compose exec -T mage python /home/src/powerbi/scripts/build_map_shapes.py
hoặc: .\\tasks.ps1 build-map

Đầu vào : data/reference/taxi_zones.zip (shapefile TLC, hệ tọa độ NY State Plane EPSG:2263, đơn vị feet)
Đầu ra  : powerbi/map_shapes/taxi_zones.topojson  (object "taxi_zones", thuộc tính LocationID, zone, borough)
          powerbi/map_shapes/taxi_zone_centroids.csv (LocationID, zone, borough, latitude, longitude)

Các bước: đơn giản hóa hình (SIMPLIFY_FEET) trong hệ feet → chuyển sang WGS84 (kinh độ, vĩ độ) →
làm tròn 5 chữ số thập phân (~1 m) → ghi TopoJSON không lượng tử hóa (mỗi vòng biên là một arc).
Mã khu vực 264, 265 (Unknown, Outside of NYC) không có hình trong shapefile.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SRC = "/vsizip/" + (ROOT / "data" / "reference" / "taxi_zones.zip").as_posix() + "/taxi_zones/taxi_zones.shp"
OUT = ROOT / "powerbi" / "map_shapes"
SIMPLIFY_FEET = 30
DECIMALS = 5


def ring_to_arc(ring: list[list[float]]) -> list[list[float]]:
    return [[round(x, DECIMALS), round(y, DECIMALS)] for x, y in ring]


def main() -> int:
    con = duckdb.connect()
    con.execute("install spatial; load spatial")
    rows = con.execute(f"""
        with z as (
            select LocationID as location_id, zone, borough,
                   st_transform(st_simplifypreservetopology(geom, {SIMPLIFY_FEET}),
                                'EPSG:2263', 'EPSG:4326', always_xy := true) as g
            from st_read('{SRC}')
        )
        select location_id, zone, borough, st_asgeojson(g), st_y(st_centroid(g)), st_x(st_centroid(g))
        from z
        order by location_id
    """).fetchall()

    arcs: list[list[list[float]]] = []
    geometries = []
    for location_id, zone, borough, geojson, lat, lon in rows:
        geo = json.loads(geojson)
        polygons = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
        topo_polygons = []
        for polygon in polygons:
            ring_refs = []
            for ring in polygon:
                arcs.append(ring_to_arc(ring))
                ring_refs.append([len(arcs) - 1])
            topo_polygons.append(ring_refs)
        geometry = {"type": "MultiPolygon", "arcs": topo_polygons} if len(topo_polygons) > 1 \
            else {"type": "Polygon", "arcs": topo_polygons[0]}
        geometry["properties"] = {"LocationID": location_id, "zone": zone, "borough": borough}
        geometries.append(geometry)

    topo = {"type": "Topology", "objects": {"taxi_zones": {"type": "GeometryCollection", "geometries": geometries}},
            "arcs": arcs}
    OUT.mkdir(parents=True, exist_ok=True)
    topo_path = OUT / "taxi_zones.topojson"
    topo_path.write_text(json.dumps(topo, separators=(",", ":")), encoding="utf-8")

    csv_path = OUT / "taxi_zone_centroids.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["LocationID", "zone", "borough", "latitude", "longitude"])
        for location_id, zone, borough, _geojson, lat, lon in rows:
            w.writerow([location_id, zone, borough, round(lat, 6), round(lon, 6)])

    points = sum(len(a) for a in arcs)
    print(f"{len(geometries)} khu vực, {len(arcs)} arc, {points:,} điểm")
    print(f"{topo_path.relative_to(ROOT)}: {topo_path.stat().st_size / 1024:,.0f} KB")
    print(f"{csv_path.relative_to(ROOT)}: {len(rows)} dòng")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
