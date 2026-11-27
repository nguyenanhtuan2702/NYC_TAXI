"""Xuất OLAP mart và Dimension từ DuckDB ra Parquet cho Power BI.

Chạy trong container Mage (có thư viện duckdb):
  docker compose exec -T mage python /home/src/powerbi/scripts/export_bi.py
hoặc: .\\tasks.ps1 export-bi

- Mở database ở chế độ read_only: không ghi gì vào kho dữ liệu, nhưng vẫn không chạy được khi
  pipeline Mage/dbt đang ghi (DuckDB chỉ cho một tiến trình ghi).
- Mỗi bảng ghi ra file tạm rồi đổi tên, nên Power BI không bao giờ đọc phải file ghi dở.
- Ghi data/bi/_manifest.json (thời điểm xuất, số dòng từng bảng) để đối chiếu sau khi refresh.
- Không xuất Fact (~85 triệu dòng): Power BI dùng các mart đã tổng hợp.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("DUCKDB_PATH") or ROOT / "data" / "warehouse" / "nyc_taxi.duckdb")
OUT_DIR = Path(os.environ.get("BI_EXPORT_DIR") or ROOT / "data" / "bi")

TABLES = [
    "dds.dimdate",
    "dds.dimlocation",
    "dds.dimvendor",
    "dds.dimpaymenttype",
    "dds.dimratecode",
    "dds.dimpassengergroup",
    "dds.dimdistancegroup",
    "olap.mart_trips_daily",
    "olap.mart_hourly_activity",
    "olap.mart_routes_monthly",
    "olap.mart_trip_profile",
    "olap.mart_monthly_kpi",
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("set enable_progress_bar = false")
    manifest = {"exported_at_utc": datetime.now(timezone.utc).isoformat(), "database": DB_PATH.name, "tables": {}}
    for table in TABLES:
        name = table.split(".")[1]
        target = OUT_DIR / f"{name}.parquet"
        tmp = OUT_DIR / f".{name}.parquet.tmp"
        started = time.monotonic()
        rows = con.execute(f"select count(*) from {table}").fetchone()[0]
        con.execute(f"copy (select * from {table}) to '{tmp.as_posix()}' (format parquet, compression zstd)")
        written = con.execute(f"select count(*) from read_parquet('{tmp.as_posix()}')").fetchone()[0]
        if written != rows:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"{table}: số dòng ghi ra ({written}) khác số dòng nguồn ({rows})")
        os.replace(tmp, target)
        size_kb = target.stat().st_size / 1024
        manifest["tables"][name] = {"source": table, "rows": rows, "size_kb": round(size_kb, 1)}
        print(f"{table:<28} {rows:>10,} dòng  {size_kb:>9,.1f} KB  {time.monotonic() - started:5.1f} s")
    con.close()
    (OUT_DIR / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã xuất {len(TABLES)} bảng vào {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
