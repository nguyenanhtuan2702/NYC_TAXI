#!/usr/bin/env python3
"""Runner QA chỉ đọc cho kho dữ liệu NYC Taxi trên DuckDB.

Chạy trong container Mage (có sẵn thư viện duckdb, cùng phiên bản với file dữ liệu):
  docker compose exec -T mage python /home/src/tests/run_quality_tests.py --suite smoke
hoặc từ máy host:
  .\\tasks.ps1 qa [preflight|smoke|deep|all|full]

Các suite:
  static     chỉ kiểm tra file trong repo (không mở database)
  preflight  static + mở database ở chế độ read_only
  smoke      preflight + mỗi bảng/view tồn tại, đọc được, có dữ liệu
  deep       smoke + kiểm tra hợp đồng schema, đối chiếu số dòng, khóa, SCD2, mart
  all        như deep
Thêm --include-large-scans để chạy các kiểm tra quét toàn bộ staging/Fact (vài chục giây).

Runner KHÔNG chạy ETL, DDL hay DML: database mở bằng duckdb.connect(read_only=True),
mọi lệnh ghi sẽ bị DuckDB từ chối. Kết quả lưu ở docs/test_plans_and_logs/runs/.
Mã thoát: 0 = không có FAIL/BLOCKED, 1 = có FAIL, 2 = có BLOCKED.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "test_plans_and_logs" / "runs"
DEFAULT_DB = ROOT / "data" / "warehouse" / "nyc_taxi.duckdb"
STATUSES = ["PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLICABLE"]

REQUIRED_FILES = [
    "docker-compose.yml",
    "Dockerfile",
    "requirements.txt",
    "requirements-dbt.txt",
    "mage/io_config.yaml",
    "mage/utils/duckdb_helpers.py",
    "mage/data_exporters/load_trips_to_raw.py",
    "mage/data_loaders/load_zone_lookup.py",
    "mage/data_exporters/export_zone_lookup.py",
    "sql/ddl/01_init_schemas.sql",
    "sql/ddl/02_create_raw.sql",
    "dbt/dbt_project.yml",
    "dbt/profiles.yml",
    "dbt/models/sources.yml",
    "dbt/models/staging/stg_yellow_taxi_trips.sql",
    "dbt/models/staging/stg_taxi_zone_lookup.sql",
    "dbt/snapshots/snap_taxi_zone_lookup.yml",
    "dbt/models/dds/facts/fact_taxi_trips.sql",
    "data/reference/taxi_zone_lookup.csv",
]

# Hợp đồng schema tầng raw (theo sql/ddl/02_create_raw.sql, kiểu DuckDB).
RAW_CONTRACT = {
    "raw.yellow_tripdata": {
        "vendor_id": "INTEGER", "tpep_pickup_datetime": "TIMESTAMP", "tpep_dropoff_datetime": "TIMESTAMP",
        "passenger_count": "BIGINT", "trip_distance": "DOUBLE", "ratecode_id": "BIGINT",
        "store_and_fwd_flag": "VARCHAR", "pu_location_id": "INTEGER", "do_location_id": "INTEGER",
        "payment_type": "BIGINT", "fare_amount": "DOUBLE", "extra": "DOUBLE", "mta_tax": "DOUBLE",
        "tip_amount": "DOUBLE", "tolls_amount": "DOUBLE", "improvement_surcharge": "DOUBLE",
        "total_amount": "DOUBLE", "congestion_surcharge": "DOUBLE", "airport_fee": "DOUBLE",
        "cbd_congestion_fee": "DOUBLE", "source_file_name": "VARCHAR", "source_row_number": "BIGINT",
        "batch_id": "BIGINT", "load_datetime": "TIMESTAMP",
    },
    "raw.taxi_zone_lookup": {
        "location_id": "INTEGER", "borough": "VARCHAR", "zone": "VARCHAR", "service_zone": "VARCHAR",
        "source_file_name": "VARCHAR", "batch_id": "BIGINT", "load_datetime": "TIMESTAMP",
    },
}
# Cột kiểm toán bắt buộc NOT NULL theo DDL.
RAW_NOT_NULL = [("raw.yellow_tripdata", "source_file_name"), ("raw.yellow_tripdata", "load_datetime"),
                ("raw.taxi_zone_lookup", "source_file_name"), ("raw.taxi_zone_lookup", "load_datetime")]

RELATIONS = {
    "raw": ["raw.yellow_tripdata", "raw.taxi_zone_lookup", "control.etl_control"],
    "stage": ["stage.stg_yellow_taxi_trips", "stage.stg_taxi_zone_lookup"],
    "snapshot": ["snapshots.snap_taxi_zone_lookup"],
    "fact": ["dds.facttaxitrip"],
    "olap": ["olap.mart_trips_daily", "olap.mart_hourly_activity", "olap.mart_routes_monthly",
             "olap.mart_trip_profile", "olap.mart_monthly_kpi"],
}

DIMENSIONS = [
    {"name": "DimDate", "table": "dds.dimdate", "sk": "datesk", "natural": ["fulldate"],
     "cols": ["datesk", "fulldate", "day", "dayofweek", "dayname", "weekofyear", "month", "monthname", "quarter", "year"],
     "expected_count": 763},  # 2024-01-01 .. 2026-01-31 + Unknown
    {"name": "DimTime", "table": "dds.dimtime", "sk": "timesk", "natural": ["hour", "minute"],
     "cols": ["timesk", "hour", "minute", "timeofday", "timeslot"], "expected_count": 1441},
    {"name": "DimLocation", "table": "dds.dimlocation", "sk": "locationsk", "natural": ["locationid", "versionno"],
     "cols": ["locationsk", "locationid", "borough", "zone", "servicezone", "versionno", "validfrom", "validto", "iscurrent"],
     "expected_count": None},
    {"name": "DimVendor", "table": "dds.dimvendor", "sk": "vendorsk", "natural": ["vendorid"],
     "cols": ["vendorsk", "vendorid", "vendorname"], "expected_count": None},
    {"name": "DimPaymentType", "table": "dds.dimpaymenttype", "sk": "paymenttypesk", "natural": ["paymenttypeid"],
     "cols": ["paymenttypesk", "paymenttypeid", "paymenttypename"], "expected_count": None},
    {"name": "DimRateCode", "table": "dds.dimratecode", "sk": "ratecodesk", "natural": ["ratecodeid"],
     "cols": ["ratecodesk", "ratecodeid", "ratecodename"], "expected_count": None},
    {"name": "DimPassengerGroup", "table": "dds.dimpassengergroup", "sk": "passengergroupsk", "natural": ["passengergroupcode"],
     "cols": ["passengergroupsk", "passengergroupcode", "passengergroupname", "minpassengers", "maxpassengers"],
     "expected_count": 5},  # Unknown, NONE, SINGLE, SMALL, LARGE
    {"name": "DimDistanceGroup", "table": "dds.dimdistancegroup", "sk": "distancegroupsk", "natural": ["distancegroupcode"],
     "cols": ["distancegroupsk", "distancegroupcode", "distancegroupname", "mindistance", "maxdistance"],
     "expected_count": 4},
]

# Khóa ngoại của Fact -> (bảng Dimension, cột SK).
FACT_KEYS = {
    "pickupdatesk": ("dds.dimdate", "datesk"), "dropoffdatesk": ("dds.dimdate", "datesk"),
    "pickuptimesk": ("dds.dimtime", "timesk"), "dropofftimesk": ("dds.dimtime", "timesk"),
    "pickuplocationsk": ("dds.dimlocation", "locationsk"), "dropofflocationsk": ("dds.dimlocation", "locationsk"),
    "vendorsk": ("dds.dimvendor", "vendorsk"), "paymenttypesk": ("dds.dimpaymenttype", "paymenttypesk"),
    "ratecodesk": ("dds.dimratecode", "ratecodesk"), "passengergroupsk": ("dds.dimpassengergroup", "passengergroupsk"),
    "distancegroupsk": ("dds.dimdistancegroup", "distancegroupsk"),
}

SCOPES = ["raw", "stage", "dimension", "fact", "olap"]


# --------------------------------------------------------------------------- báo cáo
class Reporter:
    def __init__(self, suite: str, scope: str, include_large_scans: bool):
        self.suite = suite
        self.scope = scope
        self.include_large_scans = include_large_scans
        self.started = datetime.now(timezone.utc)
        self.run_id = self.started.strftime("%Y%m%dT%H%M%SZ")
        self.tests: list[dict[str, Any]] = []

    def add(self, test_id: str, name: str, layer: str, status: str, expected: str,
            actual: Any = None, note: str = "", duration_ms: int | None = None) -> None:
        assert status in STATUSES, status
        self.tests.append({"test_id": test_id, "name": name, "layer": layer, "status": status,
                           "expected": expected, "actual": actual, "note": note, "duration_ms": duration_ms})

    def counts(self) -> dict[str, int]:
        return {key: sum(1 for t in self.tests if t["status"] == key) for key in STATUSES}

    def overall(self) -> str:
        c = self.counts()
        if c["FAIL"]:
            return "FAIL"
        if c["BLOCKED"]:
            return "BLOCKED"
        if c["NOT RUN"]:
            return "PARTIAL"
        return "PASS"

    def save(self) -> tuple[Path, Path]:
        RESULTS.mkdir(parents=True, exist_ok=True)
        json_path = RESULTS / f"run_{self.run_id}.json"
        md_path = RESULTS / f"run_{self.run_id}.md"
        finished = datetime.now(timezone.utc)
        payload = {
            "run_id": self.run_id, "started_at_utc": self.started.isoformat(),
            "finished_at_utc": finished.isoformat(), "engine": "duckdb", "suite": self.suite,
            "scope": self.scope, "read_only": True, "large_table_scans_enabled": self.include_large_scans,
            "overall_status": self.overall(), "counts": self.counts(), "tests": self.tests,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        c = self.counts()
        lines = [
            f"# Lượt kiểm thử QA {self.run_id}", "",
            f"- Suite: `{self.suite}`", f"- Phạm vi: `{self.scope}`", "- Engine: DuckDB (read_only)",
            f"- Kết quả chung: **{self.overall()}**",
            f"- Quét toàn bảng lớn: **{'bật' if self.include_large_scans else 'tắt'}**", "",
            "## Tổng hợp", "",
            "| " + " | ".join(STATUSES) + " |", "|" + "---:|" * len(STATUSES),
            "| " + " | ".join(str(c[s]) for s in STATUSES) + " |", "",
            "## Kết quả", "",
            "| Mã | Tầng | Trạng thái | Kiểm tra | Kỳ vọng | Thực tế / ghi chú | ms |",
            "|---|---|---|---|---|---|---:|",
        ]
        for t in self.tests:
            detail = " ".join(str(x) for x in [t["actual"], t["note"]] if x not in (None, ""))
            detail = detail.replace("|", "\\|").replace("\n", " ")
            expected = str(t["expected"]).replace("|", "\\|").replace("\n", " ")
            ms = "" if t["duration_ms"] is None else str(t["duration_ms"])
            lines.append(f"| {t['test_id']} | {t['layer']} | **{t['status']}** | {t['name']} | {expected} | {detail} | {ms} |")
        lines += ["", f"Tạo lúc {finished.isoformat()} (UTC). Không chạy ETL, DDL hay DML.", ""]
        md_path.write_text("\n".join(lines), encoding="utf-8")
        return json_path, md_path


def timed(r: Reporter, test_id: str, name: str, layer: str, expected: str,
          fn: Callable[[], tuple[str, Any] | tuple[str, Any, str]]) -> str:
    """Chạy một kiểm tra; fn trả (status, actual[, note]). Lỗi truy vấn được ghi FAIL."""
    started = time.monotonic()
    try:
        result = fn()
        status, actual = result[0], result[1]
        note = result[2] if len(result) > 2 else ""
    except Exception as exc:  # lỗi truy vấn là lỗi kiểm thử, không làm dừng runner
        status, actual, note = "FAIL", None, f"{type(exc).__name__}: {str(exc)[:300]}"
    r.add(test_id, name, layer, status, expected, actual, note, int((time.monotonic() - started) * 1000))
    return status


# --------------------------------------------------------------------------- tiện ích DB
def db_path() -> Path:
    return Path(os.environ.get("DUCKDB_PATH") or DEFAULT_DB)


def q(conn: Any, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    return conn.execute(sql, params or []).fetchall()


def q1(conn: Any, sql: str, params: list[Any] | None = None) -> Any:
    return q(conn, sql, params)[0][0]


def relation_exists(conn: Any, relation: str) -> bool:
    schema, name = relation.split(".")
    return bool(q1(conn, """
        select count(*) from information_schema.tables where table_schema = ? and table_name = ?
    """, [schema, name]))


def columns(conn: Any, relation: str) -> dict[str, tuple[str, str]]:
    schema, name = relation.split(".")
    rows = q(conn, """
        select column_name, data_type, is_nullable from information_schema.columns
        where table_schema = ? and table_name = ?
    """, [schema, name])
    return {c: (t, n) for c, t, n in rows}


# --------------------------------------------------------------------------- preflight
def run_static_preflight(r: Reporter) -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    r.add("PF-REPO-01", "File cần thiết của repo", "Preflight", "PASS" if not missing else "FAIL",
          "DDL, pipeline Mage, project dbt và Zone CSV có trong repo",
          actual="đủ" if not missing else f"thiếu: {', '.join(missing)}")

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").lower()
    has_postgres = "image: postgres" in compose or "\n  postgres:" in compose
    has_duckdb = "duckdb_path" in compose
    r.add("PF-ENGINE-01", "Engine kho dữ liệu là DuckDB", "Preflight",
          "PASS" if has_duckdb and not has_postgres else "FAIL",
          "docker-compose.yml cấu hình DUCKDB_PATH và không còn service PostgreSQL",
          actual=f"duckdb_path={has_duckdb}; postgres_service={has_postgres}")

    docker = which("docker")
    if Path("/.dockerenv").exists():
        r.add("PF-COMPOSE-01", "docker compose config hợp lệ", "Preflight", "NOT APPLICABLE",
              "Kiểm tra khi chạy runner trên máy host", note="Runner đang chạy trong container.")
    elif docker is None:
        r.add("PF-COMPOSE-01", "docker compose config hợp lệ", "Preflight", "BLOCKED",
              "Docker CLI có sẵn", note="Không tìm thấy Docker CLI")
    else:
        proc = subprocess.run([docker, "compose", "config", "--quiet"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        r.add("PF-COMPOSE-01", "docker compose config hợp lệ", "Preflight",
              "PASS" if proc.returncode == 0 else "FAIL", "docker compose config --quiet thành công",
              actual="hợp lệ" if proc.returncode == 0 else proc.stderr.strip()[:300])


def open_readonly_connection(r: Reporter) -> Any:
    try:
        import duckdb
    except ImportError:
        r.add("PF-DB-DRIVER", "Thư viện duckdb", "Preflight", "BLOCKED", "duckdb 1.5.x import được",
              note="Không có duckdb; chạy runner trong container Mage (.\\tasks.ps1 qa).")
        return None
    version_ok = duckdb.__version__.startswith("1.5.")
    r.add("PF-DB-DRIVER", "Thư viện duckdb", "Preflight", "PASS" if version_ok else "FAIL",
          "duckdb 1.5.x (cùng phiên bản với Mage và dbt)", actual=duckdb.__version__)

    path = db_path()
    if not path.is_file():
        r.add("PF-DB-CONNECT", "Mở file DuckDB", "Preflight", "BLOCKED", "File database tồn tại",
              actual=str(path), note="Chưa chạy ingestion?")
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
        conn.execute("set enable_progress_bar = false")
    except Exception as exc:
        r.add("PF-DB-CONNECT", "Mở file DuckDB", "Preflight", "BLOCKED", "Mở được ở chế độ read_only",
              actual=str(path), note=f"{type(exc).__name__}: {str(exc)[:300]} (pipeline Mage/dbt đang ghi?)")
        return None
    size_gb = path.stat().st_size / 1024 ** 3
    r.add("PF-DB-CONNECT", "Mở file DuckDB", "Preflight", "PASS", "Mở được ở chế độ read_only",
          actual=f"{path.name}; {size_gb:.2f} GB")

    # Chứng minh không ghi được: lệnh tạo bảng phải bị từ chối.
    try:
        conn.execute("create table main.__qa_write_probe (x integer)")
        r.add("PF-DB-READONLY", "Kết nối chỉ đọc", "Preflight", "FAIL", "Lệnh ghi bị từ chối",
              actual="lệnh ghi được chấp nhận")
    except Exception as exc:
        r.add("PF-DB-READONLY", "Kết nối chỉ đọc", "Preflight", "PASS", "Lệnh ghi bị từ chối",
              actual=type(exc).__name__)
    return conn


# --------------------------------------------------------------------------- smoke
def run_smoke(r: Reporter, conn: Any, scopes: list[str]) -> dict[str, bool]:
    """Trả về {tên tầng/bảng: smoke đạt} để gate các kiểm tra deep."""
    ok: dict[str, bool] = {}
    layer_of = {"raw": "raw", "stage": "stage", "fact": "fact", "olap": "olap", "snapshot": "dimension"}
    for group, relations in RELATIONS.items():
        if layer_of[group] not in scopes:
            continue
        for rel in relations:
            def check(rel: str = rel) -> tuple[str, Any]:
                if not relation_exists(conn, rel):
                    return "FAIL", "không tồn tại"
                n = q1(conn, f"select count(*) from {rel}")
                return ("PASS" if n > 0 else "FAIL"), f"rows={n:,}"
            status = timed(r, f"SM-{rel}", f"{rel} tồn tại và có dữ liệu", f"Smoke {group}",
                           "Đọc được, số dòng > 0", check)
            ok[rel] = status == "PASS"
    if "dimension" in scopes:
        for d in DIMENSIONS:
            def check_dim(d: dict[str, Any] = d) -> tuple[str, Any, str]:
                if not relation_exists(conn, d["table"]):
                    return "FAIL", "không tồn tại", ""
                missing = [c for c in d["cols"] if c not in columns(conn, d["table"])]
                unknown = q1(conn, f"select count(*) from {d['table']} where {d['sk']} = -1")
                good = not missing and unknown == 1
                return ("PASS" if good else "FAIL"), f"unknown_rows={unknown}", (f"thiếu cột {missing}" if missing else "")
            status = timed(r, f"SM-{d['name']}", f"{d['name']} đủ cột và có đúng một dòng Unknown (-1)",
                           "Smoke dimension", "Đủ cột; một dòng SK = -1", check_dim)
            ok[d["name"]] = status == "PASS"
    return ok


# --------------------------------------------------------------------------- deep: raw
def deep_raw(r: Reporter, conn: Any, large: bool) -> None:
    layer = "Deep raw"
    for i, (rel, contract) in enumerate(RAW_CONTRACT.items(), start=1):
        def check(rel: str = rel, contract: dict[str, str] = contract) -> tuple[str, Any]:
            actual = {c: t for c, (t, _n) in columns(conn, rel).items()}
            missing = sorted(set(contract) - set(actual))
            extra = sorted(set(actual) - set(contract))
            mismatch = sorted(c for c in set(contract) & set(actual) if contract[c] != actual[c])
            good = not (missing or extra or mismatch)
            return ("PASS" if good else "FAIL"), f"cột={len(actual)}; thiếu={missing}; thừa={extra}; sai_kiểu={mismatch}"
        timed(r, f"RAW-SCH-{i:02d}", f"Hợp đồng schema {rel}", layer, "Cột và kiểu khớp sql/ddl/02_create_raw.sql", check)

    def not_null() -> tuple[str, Any]:
        bad = [f"{rel}.{col}" for rel, col in RAW_NOT_NULL if columns(conn, rel).get(col, ("", "YES"))[1] != "NO"]
        return ("PASS" if not bad else "FAIL"), f"cột cho phép NULL: {bad}"
    timed(r, "RAW-CMP-01", "Cột kiểm toán NOT NULL theo schema", layer,
          "source_file_name, load_datetime NOT NULL ở cả hai bảng raw", not_null)

    def control() -> tuple[str, Any]:
        bad_counts, bad_rejects, success, total = q(conn, """
            select count(*) filter (where status = 'SUCCESS' and rows_read is distinct from rows_loaded),
                   count(*) filter (where status = 'SUCCESS' and coalesce(rows_rejected, 0) <> 0),
                   count(*) filter (where status = 'SUCCESS'), count(*)
            from control.etl_control
        """)[0]
        if success == 0:
            return "NOT APPLICABLE", "chưa có lượt nạp SUCCESS"
        return ("PASS" if bad_counts == bad_rejects == 0 else "FAIL"), \
            f"success={success}; tổng={total}; lệch_số_dòng={bad_counts}; có_reject={bad_rejects}"
    timed(r, "RAW-REC-01", "Nhật ký nạp thành công tự khớp", layer,
          "Lượt SUCCESS có rows_read = rows_loaded, rows_rejected = 0", control)

    def latest_failed() -> tuple[str, Any]:
        rows = q(conn, """
            select source_file_name from control.etl_control
            qualify row_number() over (partition by source_file_name order by control_id desc) = 1
               and status <> 'SUCCESS'
        """)
        return ("PASS" if not rows else "FAIL"), f"file_có_lượt_cuối_lỗi={[x[0] for x in rows]}"
    timed(r, "RAW-REC-02", "Lượt nạp gần nhất của mỗi file đều SUCCESS", layer,
          "Không file nào có lượt nạp cuối cùng FAILED", latest_failed)

    def file_counts() -> tuple[str, Any]:
        n = q1(conn, """
            with latest as (
                select source_file_name, rows_loaded from control.etl_control
                where status = 'SUCCESS' and pipeline_name = 'ingest_yellow_trips'
                qualify row_number() over (partition by source_file_name order by control_id desc) = 1
            ), observed as (
                select source_file_name, count(*) as n from raw.yellow_tripdata group by 1
            )
            select count(*) from latest l full join observed o using (source_file_name)
            where l.rows_loaded is distinct from o.n
        """)
        files = q1(conn, "select count(distinct source_file_name) from raw.yellow_tripdata")
        return ("PASS" if n == 0 else "FAIL"), f"file={files}; file_lệch={n}"
    timed(r, "RAW-REC-03", "Số dòng raw theo file = lượt nạp SUCCESS gần nhất", layer,
          "Mỗi file: count(*) trong raw = rows_loaded của lượt nạp cuối", file_counts)

    def row_numbers() -> tuple[str, Any]:
        bad = q(conn, """
            select source_file_name from raw.yellow_tripdata group by 1
            having min(source_row_number) <> 1 or max(source_row_number) <> count(*)
                or sum(source_row_number) <> count(*)::hugeint * (count(*) + 1) / 2
        """)
        return ("PASS" if not bad else "FAIL"), f"file_lỗi={[x[0] for x in bad]}"
    timed(r, "RAW-DUP-01", "source_row_number liên tục 1..N trong mỗi file", layer,
          "Không nạp trùng, không mất dòng (min = 1, max = N, sum = N(N+1)/2)", row_numbers)


# --------------------------------------------------------------------------- deep: stage
def deep_stage(r: Reporter, conn: Any, large: bool) -> None:
    layer = "Deep stage"

    def same_count() -> tuple[str, Any]:
        raw_n = q1(conn, "select count(*) from raw.yellow_tripdata")
        stg_n = q1(conn, "select count(*) from stage.stg_yellow_taxi_trips")
        return ("PASS" if raw_n == stg_n else "FAIL"), f"raw={raw_n:,}; stage={stg_n:,}"
    timed(r, "STG-REC-01", "Staging giữ đủ dòng của raw", layer, "count(stage) = count(raw)", same_count)

    def zone_unique() -> tuple[str, Any]:
        dup, nulls = q(conn, """
            select count(*) - count(distinct location_id), count(*) filter (where location_id is null)
            from stage.stg_taxi_zone_lookup
        """)[0]
        return ("PASS" if dup == nulls == 0 else "FAIL"), f"trùng={dup}; null={nulls}"
    timed(r, "STG-KEY-01", "location_id của Zone Lookup duy nhất, không NULL", layer, "0 trùng, 0 NULL", zone_unique)

    if not large:
        r.add("STG-VAL-01", "Thống kê cờ chất lượng staging", layer, "NOT RUN",
              "Quét toàn bộ view staging; chạy với --include-large-scans")
        return

    def flags() -> tuple[str, Any, str]:
        cols = [c for c in columns(conn, "stage.stg_yellow_taxi_trips") if c.startswith("is_")]
        exprs = ", ".join(f"count(*) filter (where {c}) as {c}" for c in cols)
        null_exprs = " + ".join(f"count(*) filter (where {c} is null)" for c in cols)
        row = q(conn, f"select count(*), {exprs}, {null_exprs} from stage.stg_yellow_taxi_trips")[0]
        total, counts, null_flags = row[0], dict(zip(cols, row[1:-1])), row[-1]
        metrics = {"rows": total, **counts}
        # Cờ phải luôn true/false; số dòng của từng cờ chỉ được ghi nhận (không có ngưỡng nghiệp vụ).
        return ("PASS" if null_flags == 0 else "FAIL"), metrics, f"giá_trị_NULL_trong_cờ={null_flags}"
    timed(r, "STG-VAL-01", "Thống kê cờ chất lượng staging (cờ không NULL)", layer,
          "Mọi cờ is_* là true/false; ghi nhận số dòng từng cờ", flags)


# --------------------------------------------------------------------------- deep: dimension
def deep_dimension(r: Reporter, conn: Any, smoke: dict[str, bool], large: bool) -> None:
    layer = "Deep dimension"
    for d in DIMENSIONS:
        if not smoke.get(d["name"]):
            r.add(f"DIM-SCH-{d['name']}", f"{d['name']}: SK, khóa tự nhiên, Unknown", layer, "BLOCKED",
                  "Smoke của Dimension đạt trước", note="Smoke chưa đạt")
            continue

        def keys(d: dict[str, Any] = d) -> tuple[str, Any]:
            nat = ", ".join(d["natural"])
            null_nat = " or ".join(f"{c} is null" for c in d["natural"])
            rows, null_sk, dup_sk, null_natural = q(conn, f"""
                select count(*), count(*) filter (where {d['sk']} is null),
                       count(*) - count(distinct {d['sk']}), count(*) filter (where {null_nat})
                from {d['table']}
            """)[0]
            dup_nat = q1(conn, f"select count(*) from (select {nat} from {d['table']} group by all having count(*) > 1)")
            good = null_sk == dup_sk == null_natural == dup_nat == 0
            if d["expected_count"] is not None:
                good = good and rows == d["expected_count"]
            exp = f"; kỳ_vọng_rows={d['expected_count']}" if d["expected_count"] is not None else ""
            return ("PASS" if good else "FAIL"), \
                f"rows={rows}{exp}; sk_null={null_sk}; sk_trùng={dup_sk}; nk_null={null_natural}; nk_trùng={dup_nat}"
        timed(r, f"DIM-SCH-{d['name']}", f"{d['name']}: SK, khóa tự nhiên, số dòng", layer,
              f"SK và ({', '.join(d['natural'])}) không NULL, không trùng" +
              (f"; {d['expected_count']} dòng" if d["expected_count"] else ""), keys)

    if smoke.get("DimLocation"):
        def scd2() -> tuple[str, Any]:
            bad = q(conn, """
                with v as (
                    select locationid, versionno, validfrom, validto, iscurrent,
                           lead(validfrom) over (partition by locationid order by versionno) as next_from
                    from dds.dimlocation
                )
                select
                    (select count(*) from (select locationid from v group by 1
                                           having count(*) filter (where iscurrent) <> 1)),
                    count(*) filter (where next_from is not null and next_from <> validto),
                    count(*) filter (where versionno = 1 and validfrom <> timestamp '1900-01-01'),
                    count(*) filter (where iscurrent and validto <> timestamp '9999-12-31'),
                    count(*) filter (where versionno > 1)
                from v
            """)[0]
            cur, gap, first, open_to, extra_versions = bad
            good = cur == gap == first == open_to == 0
            return ("PASS" if good else "FAIL"), (f"id_sai_số_bản_hiện_hành={cur}; khe_hở/chồng_lấn={gap}; "
                                                  f"bản_đầu_sai_validfrom={first}; bản_hiện_hành_sai_validto={open_to}; "
                                                  f"số_phiên_bản_cũ={extra_versions}")
        timed(r, "DIM-SCD-01", "DimLocation SCD Type 2 hợp lệ", layer,
              "Mỗi LocationID: đúng 1 bản hiện hành, các bản nối liền, bản đầu từ 1900-01-01", scd2)

        def snapshot_match() -> tuple[str, Any]:
            snap, dim = q(conn, """
                select (select count(*) from snapshots.snap_taxi_zone_lookup),
                       (select count(*) from dds.dimlocation where locationsk <> -1)
            """)[0]
            return ("PASS" if snap == dim else "FAIL"), f"snapshot={snap}; dimlocation(trừ Unknown)={dim}"
        timed(r, "DIM-SCD-02", "DimLocation có đủ mọi phiên bản của snapshot", layer,
              "Số dòng snapshot = số dòng DimLocation (trừ Unknown)", snapshot_match)

    def labels() -> tuple[str, Any]:
        v, p, rc = q(conn, """
            select (select count(*) from dds.dimvendor where vendorid not in (1, 2, -1) and vendorname <> 'Unknown'),
                   (select count(*) from dds.dimpaymenttype where paymenttypeid = 0 and paymenttypename <> 'Unknown'),
                   (select count(*) from dds.dimratecode where ratecodeid = 99 and ratecodename <> 'Unknown')
        """)[0]
        return ("PASS" if v == p == rc == 0 else "FAIL"), f"vendor_sai={v}; payment_sai={p}; ratecode_sai={rc}"
    timed(r, "DIM-MAP-02", "Chuẩn hóa nhãn Unknown", layer,
          "Vendor ngoài 1/2, payment 0, ratecode 99 mang nhãn Unknown", labels)

    if not large:
        r.add("DIM-MAP-01", "Mọi mã trong staging có trong Dimension", layer, "NOT RUN",
              "Quét toàn bộ staging; chạy với --include-large-scans")
        return

    def mapping() -> tuple[str, Any]:
        misses = q(conn, """
            select
              (select count(distinct s.location_id) from stage.stg_taxi_zone_lookup s
                 where not exists (select 1 from dds.dimlocation d where d.locationid = s.location_id and d.iscurrent)),
              (select count(distinct vendor_id) from stage.stg_yellow_taxi_trips s where vendor_id is not null
                 and not exists (select 1 from dds.dimvendor d where d.vendorid = s.vendor_id)),
              (select count(distinct payment_type) from stage.stg_yellow_taxi_trips s where payment_type is not null
                 and not exists (select 1 from dds.dimpaymenttype d where d.paymenttypeid = s.payment_type)),
              (select count(distinct coalesce(ratecode_id, 99)) from stage.stg_yellow_taxi_trips s
                 where not exists (select 1 from dds.dimratecode d where d.ratecodeid = coalesce(s.ratecode_id, 99)))
        """)[0]
        names = ["location", "vendor", "payment", "ratecode"]
        detail = "; ".join(f"{n}_thiếu={m}" for n, m in zip(names, misses))
        return ("PASS" if not any(misses) else "FAIL"), detail
    timed(r, "DIM-MAP-01", "Mọi mã trong staging có trong Dimension", layer,
          "Location, vendor, payment, ratecode của staging đều có dòng Dimension", mapping)


# --------------------------------------------------------------------------- deep: fact
def deep_fact(r: Reporter, conn: Any, large: bool) -> None:
    layer = "Deep fact"

    def unknown_keys() -> tuple[str, Any]:
        exprs = ", ".join(f"count(*) filter (where {k} = -1) as {k}" for k in FACT_KEYS)
        row = q(conn, f"select {exprs} from dds.facttaxitrip")[0]
        counts = {k: v for k, v in zip(FACT_KEYS, row) if v}
        return ("PASS" if not counts else "FAIL"), (counts or "không có khóa -1")
    timed(r, "FACT-KEY-01", "Fact không có khóa Unknown (-1)", layer,
          "0 dòng -1 ở cả 11 khóa (sau khi thêm nhóm NONE và mở rộng DimDate)", unknown_keys)

    def measures() -> tuple[str, Any]:
        row = q(conn, """
            select count(*) filter (where totaltrips <> 1),
                   count(*) filter (where dropoffdatetime <= pickupdatetime),
                   count(*) filter (where pickupdatetime < timestamp '2024-01-01' or pickupdatetime >= timestamp '2026-01-01'),
                   count(*) filter (where fareamount < 0 or totalamount < 0 or tripdistance < 0),
                   count(*) filter (where totalamount is null or fareamount is null)
            from dds.facttaxitrip
        """)[0]
        names = ["totaltrips_khác_1", "trả_không_sau_đón", "đón_ngoài_2024_2025", "giá_trị_âm", "tiền_null"]
        detail = dict(zip(names, row))
        return ("PASS" if not any(row) else "FAIL"), detail
    timed(r, "FACT-VAL-01", "Measure của Fact tuân thủ quy tắc is_valid_for_fact", layer,
          "TotalTrips = 1; trả sau đón; đón trong 2024–2025; tiền, quãng đường không âm", measures)

    if not large:
        for test_id, name in [("FACT-REC-01", "Fact theo file khớp staging is_valid_for_fact"),
                              ("FACT-REF-01", "Mọi khóa của Fact có trong Dimension")]:
            r.add(test_id, name, layer, "NOT RUN", "Quét toàn bộ staging/Fact; chạy với --include-large-scans")
        return

    def per_file() -> tuple[str, Any]:
        rows = q(conn, """
            with s as (select source_file_name f, count(*) n, sum(source_row_number) rn
                       from stage.stg_yellow_taxi_trips where is_valid_for_fact group by 1),
                 t as (select sourcefilename f, count(*) n, sum(sourcerownumber) rn
                       from dds.facttaxitrip group by 1)
            select coalesce(s.f, t.f), s.n, t.n from s full join t on s.f = t.f
            where s.n is distinct from t.n or s.rn is distinct from t.rn
        """)
        total = q1(conn, "select count(*) from dds.facttaxitrip")
        return ("PASS" if not rows else "FAIL"), f"fact_rows={total:,}; file_lệch={rows}"
    # So cả số dòng và tổng source_row_number theo file: bắt nạp trùng, mất dòng do join, dòng bị
    # thay bằng dòng khác, file thiếu/thừa. Rẻ hơn nhiều so với đếm distinct (file, row) trên ~85 triệu dòng.
    timed(r, "FACT-REC-01", "Fact theo file khớp staging is_valid_for_fact", layer,
          "Mỗi file: số dòng và tổng sourcerownumber bằng staging", per_file)

    def references() -> tuple[str, Any]:
        orphans = {}
        for key, (dim, sk) in FACT_KEYS.items():
            n = q1(conn, f"select count(*) from dds.facttaxitrip f anti join {dim} d on d.{sk} = f.{key}")
            if n:
                orphans[key] = n
        return ("PASS" if not orphans else "FAIL"), (orphans or "không có khóa mồ côi")
    timed(r, "FACT-REF-01", "Mọi khóa của Fact có trong Dimension", layer,
          "0 khóa mồ côi ở cả 11 khóa ngoại", references)


# --------------------------------------------------------------------------- deep: olap
def deep_olap(r: Reporter, conn: Any) -> None:
    layer = "Deep olap"

    def reconcile() -> tuple[str, Any]:
        f_trips, f_pax, f_rev = q(conn, """
            select sum(totaltrips), sum(passengercount), sum(totalamount) from dds.facttaxitrip
        """)[0]
        bad = {}
        marts = [(m, "") for m in ["mart_trips_daily", "mart_routes_monthly", "mart_trip_profile", "mart_monthly_kpi"]]
        marts += [("mart_hourly_activity", "pickup"), ("mart_hourly_activity", "dropoff")]
        for mart, role in marts:
            where = f"where activity_role = '{role}'" if role else ""
            trips, pax, rev = q(conn, f"""
                select sum(total_trips), sum(total_passengers), sum(total_revenue) from olap.{mart} {where}
            """)[0]
            if trips != f_trips or pax != f_pax or rev is None or abs(rev - f_rev) >= 1:
                bad[f"{mart}{':' + role if role else ''}"] = {"trips": trips, "passengers": pax, "revenue": rev}
        return ("PASS" if not bad else "FAIL"), (bad or f"trips={f_trips:,}; revenue={f_rev:,.2f} khớp ở 6 mục")
    timed(r, "OLAP-REC-01", "Tổng của mọi mart khớp Fact", layer,
          "Số chuyến, hành khách bằng nhau; doanh thu lệch < 1 USD", reconcile)

    def kpi_months() -> tuple[str, Any]:
        n, dup, first, last, gaps = q(conn, """
            select count(*), count(*) - count(distinct month_start), min(month_start), max(month_start),
                   count(*) filter (where month_start > (select min(month_start) from olap.mart_monthly_kpi)
                                      and prev_month_trips is null)
            from olap.mart_monthly_kpi
        """)[0]
        return ("PASS" if dup == 0 and gaps == 0 else "FAIL"), \
            f"tháng={n}; từ={first}; đến={last}; trùng={dup}; tháng_thiếu_kỳ_trước={gaps}"
    timed(r, "OLAP-KPI-01", "mart_monthly_kpi: tháng duy nhất, liên tục", layer,
          "Không trùng tháng; mọi tháng (trừ tháng đầu) có số liệu tháng trước", kpi_months)


# --------------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description="Runner QA chỉ đọc cho kho NYC Taxi trên DuckDB")
    parser.add_argument("--suite", choices=["static", "preflight", "smoke", "deep", "all"], default="smoke")
    parser.add_argument("--scope", choices=["all", *SCOPES], default="all")
    parser.add_argument("--include-large-scans", action="store_true",
                        help="Chạy các kiểm tra quét toàn bộ staging/Fact (thống kê cờ, ánh xạ mã, đối chiếu theo file)")
    args = parser.parse_args()
    scopes = SCOPES if args.scope == "all" else [args.scope]
    large = args.include_large_scans

    r = Reporter(args.suite, args.scope, large)
    run_static_preflight(r)
    conn = None
    if args.suite != "static":
        conn = open_readonly_connection(r)
    if conn is not None and args.suite in ("smoke", "deep", "all"):
        smoke = run_smoke(r, conn, scopes)
        if args.suite in ("deep", "all"):
            # Gate: chỉ chạy deep của một tầng khi mọi bảng của tầng đó qua smoke.
            gates = {
                "raw": all(smoke.get(x) for x in RELATIONS["raw"]),
                "stage": all(smoke.get(x) for x in RELATIONS["raw"] + RELATIONS["stage"]),
                "fact": all(smoke.get(x) for x in RELATIONS["stage"] + RELATIONS["fact"])
                        and all(smoke.get(d["name"]) for d in DIMENSIONS),
                "olap": all(smoke.get(x) for x in RELATIONS["fact"] + RELATIONS["olap"]),
            }
            runners = [("raw", lambda: deep_raw(r, conn, large)), ("stage", lambda: deep_stage(r, conn, large)),
                       ("dimension", lambda: deep_dimension(r, conn, smoke, large)),
                       ("fact", lambda: deep_fact(r, conn, large)), ("olap", lambda: deep_olap(r, conn))]
            for scope, run in runners:
                if scope not in scopes:
                    continue
                if gates.get(scope, True):
                    run()
                else:
                    r.add(f"DEEP-{scope.upper()}", f"Kiểm tra deep tầng {scope}", f"Deep {scope}", "BLOCKED",
                          "Smoke của tầng (và tầng phụ thuộc) đạt trước", note="Smoke chưa đạt")
    elif conn is None and args.suite in ("smoke", "deep", "all"):
        r.add("SM-ALL", "Smoke/deep", "Smoke", "BLOCKED", "Mở được database", note="Preflight không mở được database")
    if conn is not None:
        conn.close()

    json_path, md_path = r.save()
    print(f"Suite: {r.suite}; phạm vi: {r.scope}; quét lớn: {large}; kết quả: {r.overall()}")
    print("Số lượng: " + ", ".join(f"{k}={v}" for k, v in r.counts().items()))
    for t in r.tests:
        if t["status"] in ("FAIL", "BLOCKED"):
            print(f"  {t['status']}: {t['test_id']} {t['name']} -> {t['actual']} {t['note']}")
    print(f"JSON: {json_path.relative_to(ROOT)}")
    print(f"Markdown: {md_path.relative_to(ROOT)}")
    c = r.counts()
    return 1 if c["FAIL"] else (2 if c["BLOCKED"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
