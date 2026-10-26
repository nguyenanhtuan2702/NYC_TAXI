#!/usr/bin/env python3
"""Read-only preflight, smoke, and deep checks for the NYC Taxi PostgreSQL repo.

Run inside the Mage container so the existing psycopg2 dependency and Compose
environment are reused:
  docker compose exec -T mage python /home/src/tests/run_quality_tests.py --suite smoke

No ETL/DDL/DML scripts are invoked. The database connection is read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "02_test_plans_and_logs" / "runs"
REQUIRED_FILES = [
    "docker-compose.yml",
    "mage/io_config.yaml",
    "mage/data_exporters/load_trips_to_stage.py",
    "mage/data_loaders/load_zone_lookup.py",
    "mage/data_exporters/export_zone_lookup.py",
    "staging/init_sql/02_create_stage.sql",
    "warehouse/01_create_dimensions.sql",
    "warehouse/02_load_dimensions.sql",
    "staging/pg_checks/02_profile_errors.sql",
]
REQUIRED_ENV = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"]
STAGE_TABLES = [
    "stage.stg_yellow_taxi_trips",
    "stage.stg_taxi_zone_lookup",
    "control.etl_control",
]

DIMENSIONS = [
    {
        "table": "dds.DimDate", "db_name": "dimdate", "name": "DimDate", "sk": "datesk", "natural": ["fulldate"],
        "cols": ["datesk", "fulldate", "day", "dayofweek", "dayname", "weekofyear", "month", "monthname", "quarter", "year"],
        "expected_count": 732, "source": None,
    },
    {
        "table": "dds.DimTime", "db_name": "dimtime", "name": "DimTime", "sk": "timesk", "natural": ["hour", "minute"],
        "cols": ["timesk", "hour", "minute", "timeofday", "timeslot"], "expected_count": 1441, "source": None,
    },
    {
        "table": "dds.DimLocation", "db_name": "dimlocation", "name": "DimLocation", "sk": "locationsk", "natural": ["locationid"],
        "cols": ["locationsk", "locationid", "borough", "zone", "servicezone"], "expected_count": None, "source": "location",
    },
    {
        "table": "dds.DimVendor", "db_name": "dimvendor", "name": "DimVendor", "sk": "vendorsk", "natural": ["vendorid"],
        "cols": ["vendorsk", "vendorid", "vendorname"], "expected_count": None, "source": "vendor",
    },
    {
        "table": "dds.DimPaymentType", "db_name": "dimpaymenttype", "name": "DimPaymentType", "sk": "paymenttypesk", "natural": ["paymenttypeid"],
        "cols": ["paymenttypesk", "paymenttypeid", "paymenttypename"], "expected_count": None, "source": "payment",
    },
    {
        "table": "dds.DimRateCode", "db_name": "dimratecode", "name": "DimRateCode", "sk": "ratecodesk", "natural": ["ratecodeid"],
        "cols": ["ratecodesk", "ratecodeid", "ratecodename"], "expected_count": None, "source": "ratecode",
    },
    {
        "table": "dds.DimPassengerGroup", "db_name": "dimpassengergroup", "name": "DimPassengerGroup", "sk": "passengergroupsk", "natural": ["passengergroupcode"],
        "cols": ["passengergroupsk", "passengergroupcode", "passengergroupname", "minpassengers", "maxpassengers"], "expected_count": 4, "source": None,
    },
    {
        "table": "dds.DimDistanceGroup", "db_name": "dimdistancegroup", "name": "DimDistanceGroup", "sk": "distancegroupsk", "natural": ["distancegroupcode"],
        "cols": ["distancegroupsk", "distancegroupcode", "distancegroupname", "mindistance", "maxdistance"], "expected_count": 4, "source": None,
    },
]


class Reporter:
    def __init__(self, suite: str, scope: str, include_large_scans: bool):
        self.suite = suite
        self.scope = scope
        self.include_large_scans = include_large_scans
        self.started = datetime.now(timezone.utc)
        self.run_id = self.started.strftime("%Y%m%dT%H%M%SZ")
        self.tests: list[dict[str, Any]] = []
        self.connection = None

    def add(self, test_id: str, name: str, layer: str, status: str, expected: str,
            actual: Any = None, note: str = "", duration_ms: int | None = None) -> None:
        self.tests.append({
            "test_id": test_id,
            "name": name,
            "layer": layer,
            "status": status,
            "expected": expected,
            "actual": actual,
            "note": note,
            "duration_ms": duration_ms,
        })

    def counts(self) -> dict[str, int]:
        keys = ["PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLICABLE"]
        return {key: sum(1 for t in self.tests if t["status"] == key) for key in keys}

    def overall(self) -> str:
        counts = self.counts()
        if counts["FAIL"]:
            return "FAIL"
        if counts["BLOCKED"]:
            return "BLOCKED"
        if counts["NOT RUN"]:
            return "PARTIAL"
        return "PASS"

    def save(self) -> tuple[Path, Path]:
        RESULTS.mkdir(parents=True, exist_ok=True)
        json_path = RESULTS / f"run_{self.run_id}.json"
        md_path = RESULTS / f"run_{self.run_id}.md"
        finished = datetime.now(timezone.utc)
        payload = {
            "run_id": self.run_id,
            "started_at_utc": self.started.isoformat(),
            "finished_at_utc": finished.isoformat(),
            "suite": self.suite,
            "scope": self.scope,
            "read_only": True,
            "large_table_scans_enabled": self.include_large_scans,
            "overall_status": self.overall(),
            "counts": self.counts(),
            "tests": self.tests,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            f"# ETL test run {self.run_id}", "",
            f"- Suite: `{self.suite}`", f"- Scope: `{self.scope}`",
            f"- Overall: **{self.overall()}**", "- Database mode: **read-only**",
            f"- Full Stage scans: **{'enabled' if self.include_large_scans else 'disabled'}**", "",
            "## Summary", "",
            "| PASS | FAIL | BLOCKED | NOT RUN | NOT APPLICABLE |",
            "|---:|---:|---:|---:|---:|",
            "| " + " | ".join(str(self.counts()[s]) for s in ["PASS", "FAIL", "BLOCKED", "NOT RUN", "NOT APPLICABLE"]) + " |", "",
            "## Results", "",
            "| Test ID | Layer | Status | Test | Expected | Actual / note |",
            "|---|---|---|---|---|---|",
        ]
        for test in self.tests:
            actual = test["actual"]
            note = test["note"]
            detail = " ".join(str(x) for x in [actual, note] if x not in (None, ""))
            detail = detail.replace("|", "\\|").replace("\n", " ")
            expected = str(test["expected"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {test['test_id']} | {test['layer']} | **{test['status']}** | {test['name']} | {expected} | {detail} |")
        lines += ["", f"Generated at {finished.isoformat()} (UTC). No ETL, DDL, or DML was executed.", ""]
        md_path.write_text("\n".join(lines), encoding="utf-8")
        return json_path, md_path


def parse_env_file() -> dict[str, str]:
    """Read local Compose settings for connection only; never include values in reports."""
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def is_container() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("USER_CODE_PATH") == "/home/src/mage"


def run_static_preflight(r: Reporter) -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    r.add("PF-REPO-01", "Required repository assets", "Preflight",
          "PASS" if not missing else "FAIL", "Stage/Dimension scripts and loader files exist",
          actual="all present" if not missing else f"missing: {', '.join(missing)}")

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").lower()
    if "postgres:17" in compose and "sqlserver" not in compose and "mssql" not in compose:
        r.add("PF-DIALECT-01", "Verify database engine", "Preflight", "PASS",
              "Use repository's configured database", "PostgreSQL 17; no SQL Server service configured",
              "The supplied task mentions SQL Server; this suite follows the repository configuration.")
    else:
        r.add("PF-DIALECT-01", "Verify database engine", "Preflight", "FAIL",
              "Use repository's configured database", "Database engine could not be confirmed from Compose")

    env_values = parse_env_file()
    configured = {**env_values, **{key: val for key, val in os.environ.items() if key in REQUIRED_ENV}}
    missing_env = [key for key in REQUIRED_ENV if not configured.get(key)]
    r.add("PF-ENV-01", "Required connection settings are present", "Preflight",
          "PASS" if not missing_env else "BLOCKED", "Required variable names configured; values kept private",
          actual="all required names present" if not missing_env else f"missing names: {', '.join(missing_env)}")

    compose_cmd = shutil_which("docker")
    if is_container():
        r.add("PF-COMPOSE-01", "Docker Compose configuration parses", "Preflight", "NOT APPLICABLE",
              "Host Compose config is validated when the runner is launched from the repository root",
              note="Runner is inside a container and cannot invoke the host Docker Compose CLI.")
    elif compose_cmd is None:
        r.add("PF-COMPOSE-01", "Docker Compose configuration parses", "Preflight", "BLOCKED",
              "Docker Compose CLI available and configuration valid", note="Docker CLI not found")
    else:
        try:
            proc = subprocess.run([compose_cmd, "compose", "config", "--quiet"], cwd=ROOT,
                                  capture_output=True, text=True, timeout=30)
            r.add("PF-COMPOSE-01", "Docker Compose configuration parses", "Preflight",
                  "PASS" if proc.returncode == 0 else "FAIL", "docker compose config --quiet succeeds",
                  actual="configuration valid" if proc.returncode == 0 else "configuration invalid",
                  note="" if proc.returncode == 0 else safe_text(proc.stderr, configured.get("POSTGRES_PASSWORD")))
        except Exception as exc:
            r.add("PF-COMPOSE-01", "Docker Compose configuration parses", "Preflight", "BLOCKED",
                  "docker compose config --quiet succeeds", note=type(exc).__name__)

    dim_ddl = (ROOT / "warehouse/01_create_dimensions.sql").read_text(encoding="utf-8").upper()
    dim_load = (ROOT / "warehouse/02_load_dimensions.sql").read_text(encoding="utf-8").upper()
    has_destructive_ddl = bool(re.search(r"\bDROP\s+TABLE\b", dim_ddl))
    has_writes = bool(re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b", dim_load))
    r.add("PF-SAFETY-01", "Write-impact scripts identified and excluded", "Preflight", "PASS",
          "Runner does not invoke ETL or mutating scripts",
          actual=f"create script contains DROP TABLE={has_destructive_ddl}; load script contains DML={has_writes}")


def shutil_which(name: str) -> str | None:
    # Local implementation to keep the runner in the standard library.
    from shutil import which
    return which(name)


def safe_text(value: str | None, password: str | None) -> str:
    text = (value or "").strip()
    if password:
        text = text.replace(password, "<redacted>")
    return text[:500]


class PsqlCursor:
    """Small read-only adapter for hosts without psycopg2; each query is rolled back."""
    description = True

    def __init__(self, connection: "PsqlConnection"):
        self.connection = connection
        self.rows: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if params:
            values = iter(params)

            def literal(value: Any) -> str:
                if value is None:
                    return "NULL"
                if isinstance(value, bool):
                    return "TRUE" if value else "FALSE"
                if isinstance(value, (int, float)):
                    return str(value)
                return "'" + str(value).replace("'", "''") + "'"

            sql, count = re.subn(r"%s", lambda _m: literal(next(values)), sql)
            if count != len(params):
                raise ValueError("SQL parameter count mismatch")
        guarded_sql = f"BEGIN READ ONLY; {sql.rstrip().rstrip(';')}; ROLLBACK;"
        proc = subprocess.run(
            [self.connection.docker, "compose", "exec", "-T", "postgres", "psql",
             "-X", "-q", "-A", "-t", "-F", "|", "-v", "ON_ERROR_STOP=1",
             "-U", self.connection.user, "-d", self.connection.database, "-c", guarded_sql],
            cwd=ROOT, capture_output=True, text=True, timeout=1800,
        )
        if proc.returncode != 0:
            raise RuntimeError(safe_text(proc.stderr, self.connection.password) or "psql query failed")
        self.rows = []
        for line in proc.stdout.splitlines():
            if not line:
                continue
            cells = line.split("|")
            self.rows.append(tuple(self.connection.parse_cell(cell) for cell in cells))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def __enter__(self) -> "PsqlCursor":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None


class PsqlConnection:
    def __init__(self, user: str, database: str, password: str | None):
        self.docker = shutil_which("docker")
        if not self.docker:
            raise RuntimeError("Docker CLI not found")
        self.user = user
        self.database = database
        self.password = password

    @staticmethod
    def parse_cell(value: str) -> Any:
        if value == "t":
            return True
        if value == "f":
            return False
        if value == "":
            return None
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
            return float(value)
        return value

    def cursor(self) -> PsqlCursor:
        return PsqlCursor(self)

    def set_session(self, readonly: bool = True, autocommit: bool = False) -> None:
        if not readonly or autocommit:
            raise ValueError("The QA runner only permits read-only transactions")

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


def get_running_compose_services(r: Reporter, password: str | None) -> set[str] | None:
    docker = shutil_which("docker")
    if docker is None:
        r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "BLOCKED",
              "Postgres service running for database checks", note="Docker CLI not found")
        r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight", "BLOCKED",
              "Mage available if an operational loader test is authorized", note="Docker CLI not found")
        return None
    try:
        proc = subprocess.run([docker, "compose", "ps", "--status", "running", "--services"],
                              cwd=ROOT, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "BLOCKED",
              "Postgres service running for database checks", note=type(exc).__name__)
        r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight", "BLOCKED",
              "Mage available if an operational loader test is authorized", note=type(exc).__name__)
        return None
    if proc.returncode != 0:
        r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "BLOCKED",
              "Postgres service running for database checks",
              note=safe_text(proc.stderr, password) or "Docker engine unavailable")
        r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight", "BLOCKED",
              "Mage available if an operational loader test is authorized", note="Docker engine unavailable")
        return None
    services = set(line.strip() for line in proc.stdout.splitlines() if line.strip())
    if "postgres" not in services:
        r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "BLOCKED",
              "Postgres service running for database checks",
              actual=f"running services: {', '.join(sorted(services)) or 'none'}")
    else:
        r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "PASS",
              "Postgres service running", actual=f"running services: {', '.join(sorted(services))}")
    if "mage" in services:
        r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight", "PASS",
              "Mage available if an operational loader test is authorized", actual="mage service running")
    else:
        r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight", "BLOCKED",
              "Mage available if an operational loader test is authorized",
              actual=f"running services: {', '.join(sorted(services)) or 'none'}",
              note="The Stage loader was not executed.")
    return services


def open_readonly_connection(r: Reporter) -> Any:
    values = parse_env_file()
    values.update({key: val for key, val in os.environ.items() if key in REQUIRED_ENV})
    missing = [key for key in REQUIRED_ENV if not values.get(key)]
    if missing:
        r.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "BLOCKED",
              "Connection succeeds using configured settings", note=f"missing names: {', '.join(missing)}")
        return None
    if not is_container():
        # Host-side execution uses psql already installed in the running Postgres
        # container. This avoids adding Python packages to the workstation.
        try:
            conn = PsqlConnection(values["POSTGRES_USER"], values["POSTGRES_DB"], values.get("POSTGRES_PASSWORD"))
            conn.set_session(readonly=True, autocommit=False)
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, current_setting('transaction_read_only')")
                db_name, user_name, read_only = cur.fetchall()[0]
            r.add("PF-DB-DRIVER", "PostgreSQL query client is available", "Preflight", "PASS",
                  "psql available through the running Postgres service", actual="container psql")
            r.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "PASS",
                  "Connection succeeds using configured settings", actual=f"database={db_name}; user={user_name}")
            r.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight",
                  "PASS" if read_only == "on" else "FAIL", "transaction_read_only=on", actual=read_only)
            return conn
        except Exception as exc:
            r.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "BLOCKED",
                  "Connection succeeds using configured settings", note=safe_text(str(exc), values.get("POSTGRES_PASSWORD")) or type(exc).__name__)
            r.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight", "BLOCKED",
                  "transaction_read_only=on", note="No connection")
            return None
    try:
        import psycopg2  # supplied by the existing Mage Docker image
    except Exception:
        r.add("PF-DB-DRIVER", "PostgreSQL driver is available", "Preflight", "BLOCKED",
              "psycopg2 available in the Mage runtime", note="Mage image is expected to install psycopg2-binary")
        return None
    host = values["POSTGRES_HOST"]
    if not is_container() and host in {"postgres", "nyc-postgres"}:
        host = "127.0.0.1"
    try:
        conn = psycopg2.connect(
            host=host,
            port=int(values["POSTGRES_PORT"]),
            dbname=values["POSTGRES_DB"],
            user=values["POSTGRES_USER"],
            password=values["POSTGRES_PASSWORD"],
            connect_timeout=5,
            application_name="nyc_taxi_readonly_qa",
        )
        conn.set_session(readonly=True, autocommit=False)
        r.connection = conn
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, current_setting('transaction_read_only')")
            db_name, user_name, read_only = cur.fetchone()
        if is_container():
            r.add("PF-STACK-01", "Required Compose services are running", "Preflight", "PASS",
                  "Postgres reachable from test runtime", actual="database service connection succeeded")
            mage_runtime = os.environ.get("USER_CODE_PATH") == "/home/src/mage"
            r.add("PF-MAGE-01", "Mage service is running for ETL execution", "Preflight",
                  "PASS" if mage_runtime else "BLOCKED", "Runner executing in Mage runtime",
                  actual="Mage runtime" if mage_runtime else "container is not identified as Mage")
        r.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "PASS",
              "Connection succeeds using configured settings", actual=f"database={db_name}; user={user_name}")
        r.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight",
              "PASS" if read_only == "on" else "FAIL", "transaction_read_only=on", actual=read_only)
        return conn
    except Exception as exc:
        password = values.get("POSTGRES_PASSWORD")
        r.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "BLOCKED",
              "Connection succeeds using configured settings", note=safe_text(str(exc), password) or type(exc).__name__)
        r.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight", "BLOCKED",
              "transaction_read_only=on", note="No connection")
        return None


def query(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def relation_exists(conn: Any, relation: str) -> bool:
    return bool(query(conn, "SELECT to_regclass(%s) IS NOT NULL", (relation,))[0][0])


def relation_estimate(conn: Any, schema: str, table: str) -> int | None:
    row = query(conn, """
        SELECT GREATEST(c.reltuples, 0)::bigint
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=%s
    """, (schema, table))
    return int(row[0][0]) if row else None


def add_blocked_smoke(r: Reporter, scope: str, reason: str) -> None:
    if scope in ("all", "stage"):
        for test_id, name in [
            ("STG-SM-01", "Trip Stage table exists and is readable"),
            ("STG-SM-02", "Zone Lookup Stage table exists and is readable"),
            ("STG-SM-03", "ETL control table exists and is readable"),
            ("STG-SM-04", "Source inputs and loader files are available"),
            ("STG-ETL-01", "Stage ETL execution in an isolated target"),
        ]:
            r.add(test_id, name, "Stage Smoke", "BLOCKED", "Read-only database check", note=reason)
    if scope in ("all", "dimension"):
        for d in DIMENSIONS:
            r.add(f"DIM-SM-{d['name']}", f"{d['name']} exists, is readable, and has Unknown member",
                  "Dimension Smoke", "BLOCKED", "Read-only database check", note=reason)


def smoke_stage(r: Reporter, conn: Any) -> bool:
    relation_specs = [
        ("STG-SM-01", "Trip Stage table exists and is readable", "stage.stg_yellow_taxi_trips", "stage", "stg_yellow_taxi_trips"),
        ("STG-SM-02", "Zone Lookup Stage table exists and is readable", "stage.stg_taxi_zone_lookup", "stage", "stg_taxi_zone_lookup"),
        ("STG-SM-03", "ETL control table exists and is readable", "control.etl_control", "control", "etl_control"),
    ]
    ok_all = True
    for test_id, name, rel, schema, table in relation_specs:
        started = time.monotonic()
        try:
            exists = relation_exists(conn, rel)
            if not exists:
                r.add(test_id, name, "Stage Smoke", "FAIL", f"{rel} exists and can be queried", actual="relation missing")
                ok_all = False
                continue
            row = query(conn, f"SELECT 1 FROM {rel} LIMIT 1")
            metric = (f"estimated_rows={relation_estimate(conn, schema, table)}" if table == "stg_yellow_taxi_trips"
                      else f"exact_rows={query(conn, f'SELECT count(*) FROM {rel}')[0][0]}")
            r.add(test_id, name, "Stage Smoke", "PASS", f"{rel} exists and can be queried",
                  actual=f"readable; {metric}; has_row={bool(row)}",
                  note="Trip row count is a planner estimate; other counts are exact.",
                  duration_ms=int((time.monotonic()-started)*1000))
        except Exception as exc:
            r.add(test_id, name, "Stage Smoke", "FAIL", f"{rel} can be queried", note=type(exc).__name__)
            ok_all = False
    csv_ok = (ROOT / "data/reference/taxi_zone_lookup.csv").is_file()
    parquet_files = list((ROOT / "data/raw").glob("*.parquet")) if (ROOT / "data/raw").exists() else []
    loader_ok = (ROOT / "mage/data_exporters/load_trips_to_stage.py").is_file()
    r.add("STG-SM-04", "Source inputs and loader files are available", "Stage Smoke",
          "PASS" if csv_ok and loader_ok else "FAIL",
          "Zone CSV and Mage loader present; no source download performed",
          actual=f"zone_csv={csv_ok}; parquet_files_present={len(parquet_files)}; trip_loader={loader_ok}",
          note="Missing Parquet files are normally downloaded by the loader; this smoke test does not download or load them.")
    r.add("STG-ETL-01", "Stage ETL execution in an isolated target", "Stage Smoke", "BLOCKED",
          "Execute the loader only against a disposable database",
          note="The loader performs DELETE/COPY writes. No isolated test database is configured, and the Mage service is not running.")
    return ok_all and csv_ok and loader_ok


def smoke_dimensions(r: Reporter, conn: Any) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for d in DIMENSIONS:
        test_id = f"DIM-SM-{d['name']}"
        try:
            exists = relation_exists(conn, d["table"])
            if not exists:
                r.add(test_id, f"{d['name']} exists, is readable, and has Unknown member", "Dimension Smoke",
                      "FAIL", "Dimension relation exists", actual="relation missing")
                results[d["name"]] = False
                continue
            cols = query(conn, """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='dds' AND table_name=%s
            """, (d["db_name"],))
            actual_cols = {row[0] for row in cols}
            missing_cols = [col for col in d["cols"] if col not in actual_cols]
            row = query(conn, f"SELECT 1 FROM {d['table']} LIMIT 1")
            unknown = query(conn, f"SELECT 1 FROM {d['table']} WHERE {d['sk']}=-1 LIMIT 1")
            good = not missing_cols and bool(row) and bool(unknown)
            note = f"missing_columns={missing_cols}" if missing_cols else ""
            r.add(test_id, f"{d['name']} exists, is readable, and has Unknown member", "Dimension Smoke",
                  "PASS" if good else "FAIL", "Required columns readable and one SK=-1 member exists",
                  actual=f"readable={bool(row)}; unknown_member={bool(unknown)}", note=note)
            results[d["name"]] = good
        except Exception as exc:
            r.add(test_id, f"{d['name']} exists, is readable, and has Unknown member", "Dimension Smoke",
                  "FAIL", "Read-only query succeeds", note=type(exc).__name__)
            results[d["name"]] = False
    return results


def run_smoke(r: Reporter, conn: Any, scope: str) -> tuple[bool, dict[str, bool]]:
    if conn is None:
        add_blocked_smoke(r, scope, "Preflight did not establish a safe database connection.")
        return False, {}
    stage_ok = True
    dimensions_ok: dict[str, bool] = {}
    if scope in ("all", "stage"):
        stage_ok = smoke_stage(r, conn)
    if scope in ("all", "dimension"):
        dimensions_ok = smoke_dimensions(r, conn)
    return stage_ok, dimensions_ok


def blocked_deep(r: Reporter, scope: str, reason: str) -> None:
    if scope in ("all", "stage"):
        for test_id, name in [
            ("STG-SCH-01", "Stage schema contract"),
            ("STG-CMP-01", "Required audit fields are non-null by schema"),
            ("STG-REC-01", "Successful ETL control rows reconcile"),
            ("STG-VAL-01", "Stage quality profile metrics"),
            ("STG-DUP-01", "Source row numbers are unique per file"),
            ("STG-REC-02", "Stage row counts reconcile to latest successful loads"),
        ]:
            r.add(test_id, name, "Stage Deep", "BLOCKED", "Read-only SQL assertion", note=reason)
    if scope in ("all", "dimension"):
        for d in DIMENSIONS:
            r.add(f"DIM-SCH-{d['name']}", f"{d['name']} schema, SK, natural key, Unknown, and uniqueness",
                  "Dimension Deep", "BLOCKED", "Read-only SQL assertions", note=reason)
        for test_id, name in [
            ("DIM-MAP-01", "Stage natural keys map to their Dimensions"),
            ("DIM-MAP-02", "Vendor/payment/rate-code normalization matches code"),
            ("DIM-IDEMP-01", "Dimension ETL idempotency in isolated test database"),
            ("NEG-FIXTURE-01", "Negative fixtures are detected by assertions"),
        ]:
            status = "BLOCKED" if test_id != "DIM-IDEMP-01" else "BLOCKED"
            r.add(test_id, name, "Dimension Deep", status, "Safe, isolated test database required", note=reason)
    r.add("FACT-INT-01", "Fact integration checks", "Integration", "BLOCKED",
          "Fact implementation exists before integration tests", note="Fact table/ETL is absent from the tracked repository.")


def deep_stage(r: Reporter, conn: Any, include_large_scans: bool) -> None:
    expected = {
        "stg_yellow_taxi_trips": {
            "vendor_id": "integer", "tpep_pickup_datetime": "timestamp without time zone",
            "tpep_dropoff_datetime": "timestamp without time zone", "passenger_count": "bigint",
            "trip_distance": "double precision", "ratecode_id": "bigint", "store_and_fwd_flag": "character varying",
            "pu_location_id": "integer", "do_location_id": "integer", "payment_type": "bigint",
            "fare_amount": "double precision", "extra": "double precision", "mta_tax": "double precision",
            "tip_amount": "double precision", "tolls_amount": "double precision", "improvement_surcharge": "double precision",
            "total_amount": "double precision", "congestion_surcharge": "double precision", "airport_fee": "double precision",
            "cbd_congestion_fee": "double precision", "source_file_name": "character varying",
            "source_row_number": "bigint", "batch_id": "bigint", "load_datetime": "timestamp without time zone",
        },
        "stg_taxi_zone_lookup": {
            "location_id": "integer", "borough": "character varying", "zone": "character varying",
            "service_zone": "character varying", "source_file_name": "character varying", "batch_id": "bigint",
            "load_datetime": "timestamp without time zone",
        },
    }
    schema_pass = True
    for index, (table, expected_cols) in enumerate(expected.items(), start=1):
        rows = query(conn, """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='stage' AND table_name=%s
        """, (table,))
        actual = {row[0]: row[1] for row in rows}
        missing = sorted(set(expected_cols) - set(actual))
        extra = sorted(set(actual) - set(expected_cols))
        mismatched = sorted(k for k in set(expected_cols) & set(actual) if expected_cols[k] != actual[k])
        good = not missing and not extra and not mismatched
        schema_pass &= good
        r.add(f"STG-SCH-{index:02d}", f"Schema contract for stage.{table}", "Stage Deep",
              "PASS" if good else "FAIL", "Expected columns and PostgreSQL types match DDL",
              actual=f"columns={len(actual)}; missing={missing}; extra={extra}; type_mismatch={mismatched}")
    required = query(conn, """
        SELECT table_name, column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema='stage' AND
              ((table_name='stg_yellow_taxi_trips' AND column_name IN ('source_file_name','load_datetime')) OR
               (table_name='stg_taxi_zone_lookup' AND column_name IN ('source_file_name','load_datetime')))
    """)
    bad_nullable = [f"{table}.{col}" for table, col, nullable in required if nullable != "NO"]
    r.add("STG-CMP-01", "Required audit fields are non-null by schema", "Stage Deep",
          "PASS" if not bad_nullable and len(required) == 4 else "FAIL",
          "source_file_name and load_datetime are NOT NULL on both Stage tables",
          actual=f"checked={len(required)}; nullable_required={bad_nullable}")

    rec = query(conn, """
        SELECT count(*) FILTER (WHERE status='SUCCESS' AND rows_read IS DISTINCT FROM rows_loaded),
               count(*) FILTER (WHERE status='SUCCESS' AND COALESCE(rows_rejected,0)<>0),
               count(*) FILTER (WHERE status='SUCCESS'), count(*)
        FROM control.etl_control
    """)[0]
    bad_counts, bad_rejects, success_count, all_count = map(int, rec)
    rec_status = "NOT APPLICABLE" if success_count == 0 else ("PASS" if bad_counts == 0 and bad_rejects == 0 else "FAIL")
    r.add("STG-REC-01", "Successful ETL control rows reconcile", "Stage Deep", rec_status,
          "Successful batches have rows_read=rows_loaded and rows_rejected=0",
          actual=f"successful={success_count}; all_control_rows={all_count}; bad_count_rows={bad_counts}; bad_reject_rows={bad_rejects}")

    if not include_large_scans:
        for test_id, name in [
            ("STG-VAL-01", "Stage quality profile metrics"),
            ("STG-DUP-01", "Source row numbers are unique per file"),
            ("STG-REC-02", "Stage row counts reconcile to latest successful loads"),
        ]:
            r.add(test_id, name, "Stage Deep", "NOT RUN", "Full Stage scan; run with --include-large-scans",
                  note="Omitted by default to avoid an unplanned full scan of the large trip table.")
        return

    started = time.monotonic()
    metrics = query(conn, """
        SELECT count(*) AS row_count,
               count(*) FILTER (WHERE tpep_pickup_datetime IS NULL) AS pickup_null,
               count(*) FILTER (WHERE tpep_dropoff_datetime IS NULL) AS dropoff_null,
               count(*) FILTER (WHERE tpep_dropoff_datetime < tpep_pickup_datetime) AS dropoff_before_pickup,
               count(*) FILTER (WHERE trip_distance<=0) AS nonpositive_distance,
               count(*) FILTER (WHERE fare_amount<0) AS negative_fare,
               count(*) FILTER (WHERE total_amount<0) AS negative_total
        FROM stage.stg_yellow_taxi_trips
    """)[0]
    metric_dict = dict(zip(["rows", "pickup_null", "dropoff_null", "dropoff_before_pickup", "nonpositive_distance", "negative_fare", "negative_total"], map(int, metrics)))
    r.add("STG-VAL-01", "Stage quality profile metrics", "Stage Deep", "NOT APPLICABLE",
          "Metrics recorded; no zero-tolerance business threshold is defined in repository",
          actual=metric_dict, note="Raw Stage preserves source anomalies; counts do not alone indicate failure.",
          duration_ms=int((time.monotonic()-started)*1000))

    started = time.monotonic()
    duplicates = int(query(conn, """
        SELECT count(*) FROM (
          SELECT source_file_name, source_row_number
          FROM stage.stg_yellow_taxi_trips
          GROUP BY source_file_name, source_row_number
          HAVING count(*)>1
        ) d
    """)[0][0])
    r.add("STG-DUP-01", "Source row numbers are unique per file", "Stage Deep",
          "PASS" if duplicates == 0 else "FAIL", "No duplicate (source_file_name, source_row_number)",
          actual=f"duplicate_keys={duplicates}", duration_ms=int((time.monotonic()-started)*1000))

    started = time.monotonic()
    mismatches = query(conn, """
        WITH latest AS (
          SELECT DISTINCT ON (source_file_name) source_file_name, rows_loaded
          FROM control.etl_control WHERE status='SUCCESS'
          ORDER BY source_file_name, control_id DESC
        ), observed AS (
          SELECT source_file_name, count(*) AS actual_rows
          FROM stage.stg_yellow_taxi_trips GROUP BY source_file_name
        )
        SELECT count(*) FROM latest l FULL JOIN observed o USING(source_file_name)
        WHERE l.rows_loaded IS DISTINCT FROM o.actual_rows
    """)[0][0]
    mismatch_count = int(mismatches)
    r.add("STG-REC-02", "Stage row counts reconcile to latest successful loads", "Stage Deep",
          "NOT APPLICABLE" if mismatch_count == 0 and not query(conn, "SELECT 1 FROM control.etl_control WHERE status='SUCCESS' LIMIT 1") else ("PASS" if mismatch_count == 0 else "FAIL"),
          "Each latest successful file log equals its Stage row count",
          actual=f"mismatched_files={mismatch_count}", duration_ms=int((time.monotonic()-started)*1000))


def deep_dimension(r: Reporter, conn: Any, smoke_results: dict[str, bool], include_large_scans: bool) -> None:
    for d in DIMENSIONS:
        if not smoke_results.get(d["name"], False):
            r.add(f"DIM-SCH-{d['name']}", f"{d['name']} key, natural key, Unknown, and uniqueness",
                  "Dimension Deep", "BLOCKED", "Dimension Smoke passes first", note="Dimension Smoke did not pass.")
            continue
        table = d["table"]
        sk = d["sk"]
        natural = d["natural"]
        nat_expr = ", ".join(natural)
        null_natural_clause = " OR ".join(f"{col} IS NULL" for col in natural)
        counts = query(conn, f"""
            SELECT count(*) FILTER (WHERE {sk} IS NULL),
                   count(*)-count(DISTINCT {sk}),
                   count(*) FILTER (WHERE {null_natural_clause}),
                   count(*) FILTER (WHERE {sk}=-1)
            FROM {table}
        """)[0]
        null_sk, duplicate_sk, null_natural, unknown_count = map(int, counts)
        natural_duplicates = int(query(conn, f"""
            SELECT count(*) FROM (
                SELECT {nat_expr} FROM {table}
                GROUP BY {nat_expr} HAVING count(*)>1
            ) d
        """)[0][0])
        expected = d["expected_count"]
        row_count = int(query(conn, f"SELECT count(*) FROM {table}")[0][0])
        good = null_sk == 0 and duplicate_sk == 0 and null_natural == 0 and natural_duplicates == 0 and unknown_count == 1
        r.add(f"DIM-SCH-{d['name']}", f"{d['name']} SK, natural key, Unknown, and uniqueness", "Dimension Deep",
              "PASS" if good else "FAIL",
              "SK/natural keys are non-null and unique; exactly one SK=-1 member exists",
              actual=f"rows={row_count}; null_sk={null_sk}; duplicate_sk={duplicate_sk}; null_natural={null_natural}; duplicate_natural_groups={natural_duplicates}; unknown_rows={unknown_count}")
        if expected is not None:
            r.add(f"DIM-COUNT-{d['name']}", f"{d['name']} generated/static row count", "Dimension Deep",
                  "PASS" if row_count == expected else "FAIL", f"Expected {expected} rows including Unknown member",
                  actual=f"rows={row_count}")

    if not include_large_scans:
        mapping_status = "BLOCKED" if not all(smoke_results.get(d["name"], False) for d in DIMENSIONS if d["source"]) else "NOT RUN"
        mapping_note = ("Source-based Dimensions did not pass Smoke." if mapping_status == "BLOCKED"
                        else "Omitted by default to avoid full scans.")
        r.add("DIM-MAP-01", "Stage natural keys map to their Dimensions", "Dimension Deep", mapping_status,
              "Large Stage scans require --include-large-scans", note=mapping_note)
        r.add("DIM-MAP-02", "Vendor/payment/rate-code normalization matches code", "Dimension Deep",
              "BLOCKED" if not all(smoke_results.get(name, False) for name in ["DimVendor", "DimPaymentType", "DimRateCode"]) else "NOT RUN",
              "Dimension Smoke passes; then check configured labels", note="Required Dimension tables are unavailable." if not all(smoke_results.get(name, False) for name in ["DimVendor", "DimPaymentType", "DimRateCode"]) else "Omitted because it is grouped with the large mapping checks.")
    elif not all(smoke_results.get(name, False) for name in ["DimLocation", "DimVendor", "DimPaymentType", "DimRateCode"]):
        r.add("DIM-MAP-01", "Stage natural keys map to their Dimensions", "Dimension Deep", "BLOCKED",
              "Source-based Dimensions pass Smoke before key mapping", note="One or more source-based Dimension tables are absent or unreadable.")
        r.add("DIM-MAP-02", "Vendor/payment/rate-code normalization matches code", "Dimension Deep", "BLOCKED",
              "Vendor, PaymentType, and RateCode pass Smoke before label assertions",
              note="One or more source-based Dimension tables are absent or unreadable.")
    else:
        mapping_checks = [
            ("DIM-MAP-location", 'SELECT count(DISTINCT s.location_id) FROM stage.stg_taxi_zone_lookup s WHERE s.location_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dds.DimLocation d WHERE d.LocationID=s.location_id)'),
            ("DIM-MAP-vendor", 'SELECT count(DISTINCT s.vendor_id) FROM stage.stg_yellow_taxi_trips s WHERE s.vendor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dds.DimVendor d WHERE d.VendorID=s.vendor_id)'),
            ("DIM-MAP-payment", 'SELECT count(DISTINCT s.payment_type) FROM stage.stg_yellow_taxi_trips s WHERE s.payment_type IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dds.DimPaymentType d WHERE d.PaymentTypeID=s.payment_type)'),
            ("DIM-MAP-ratecode", 'SELECT count(DISTINCT coalesce(s.ratecode_id,99)) FROM stage.stg_yellow_taxi_trips s WHERE NOT EXISTS (SELECT 1 FROM dds.DimRateCode d WHERE d.RateCodeID=coalesce(s.ratecode_id,99))'),
        ]
        misses = []
        for test_id, sql in mapping_checks:
            count = int(query(conn, sql)[0][0])
            if count:
                misses.append(f"{test_id}={count}")
        r.add("DIM-MAP-01", "Stage natural keys map to their Dimensions", "Dimension Deep",
              "PASS" if not misses else "FAIL", "All observed non-null Stage keys resolve to a Dimension",
              actual="no missing keys" if not misses else "; ".join(misses))

        norm = query(conn, '''
            SELECT
              (SELECT count(*) FROM dds.DimVendor WHERE VendorID IN (6,7) AND VendorName<>'Unknown'),
              (SELECT count(*) FROM dds.DimPaymentType WHERE PaymentTypeID=0 AND PaymentTypeName<>'Unknown'),
              (SELECT count(*) FROM dds.DimRateCode WHERE RateCodeID=99 AND RateCodeName<>'Unknown')
        ''')[0]
        bad_vendor, bad_payment, bad_rate = map(int, norm)
        r.add("DIM-MAP-02", "Vendor/payment/rate-code normalization matches code", "Dimension Deep",
              "PASS" if bad_vendor + bad_payment + bad_rate == 0 else "FAIL",
              "Vendor 6/7, payment 0, and ratecode 99 use Unknown labels when present",
              actual=f"bad_vendor={bad_vendor}; bad_payment={bad_payment}; bad_rate={bad_rate}")

    r.add("DIM-IDEMP-01", "Dimension ETL idempotency in isolated test database", "Dimension Deep", "BLOCKED",
          "Run twice only in a disposable isolated database",
          note="No isolated test DB is configured. DDL drops Dimension tables and DML appends rows; neither script was run.")
    r.add("NEG-FIXTURE-01", "Negative fixtures are detected by assertions", "Dimension Deep", "NOT RUN",
          "Fixture execution requires a disposable PostgreSQL database",
          note="No isolated PostgreSQL service is available; no fixture was inserted into real data.")


def run_deep(r: Reporter, conn: Any, scope: str, stage_smoke_ok: bool,
             dimension_smoke: dict[str, bool], include_large_scans: bool) -> None:
    if conn is None:
        blocked_deep(r, scope, "Smoke Test could not reach the database; dependent Deep Tests were gated.")
        return
    if scope in ("all", "stage"):
        if stage_smoke_ok:
            deep_stage(r, conn, include_large_scans)
        else:
            for test_id, name in [("STG-SCH-01", "Stage schema contract"), ("STG-CMP-01", "Required audit fields are non-null by schema"),
                                  ("STG-REC-01", "Successful ETL control rows reconcile"), ("STG-VAL-01", "Stage quality profile metrics"),
                                  ("STG-DUP-01", "Source row numbers are unique per file"), ("STG-REC-02", "Stage row counts reconcile to latest successful loads")]:
                r.add(test_id, name, "Stage Deep", "BLOCKED", "Stage Smoke passes first", note="Stage Smoke did not pass.")
    if scope in ("all", "dimension"):
        deep_dimension(r, conn, dimension_smoke, include_large_scans)
    r.add("FACT-INT-01", "Fact integration checks", "Integration", "BLOCKED",
          "Fact implementation exists before integration tests", note="Fact table/ETL is absent from the tracked repository.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only NYC Taxi Stage/Dimension QA runner")
    parser.add_argument("--suite", choices=["preflight", "smoke", "deep", "all", "static"], default="smoke")
    parser.add_argument("--scope", choices=["all", "stage", "dimension"], default="all")
    parser.add_argument("--include-large-scans", action="store_true",
                        help="Run full-table Stage profiling, duplicate, reconciliation, and key-mapping queries")
    args = parser.parse_args()
    reporter = Reporter(args.suite, args.scope, args.include_large_scans)
    run_static_preflight(reporter)
    if args.suite == "static":
        pass
    elif args.suite == "preflight":
        if not is_container():
            env = parse_env_file()
            services = get_running_compose_services(reporter, env.get("POSTGRES_PASSWORD"))
            if services is not None and "postgres" not in services:
                reporter.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "BLOCKED",
                             "Connection succeeds using configured settings", note="Postgres service is not running; connection was not attempted.")
                reporter.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight", "BLOCKED",
                             "transaction_read_only=on", note="No database connection")
            else:
                open_readonly_connection(reporter)
        else:
            open_readonly_connection(reporter)
    else:
        conn = None
        if not is_container():
            env = parse_env_file()
            services = get_running_compose_services(reporter, env.get("POSTGRES_PASSWORD"))
            if services is None or "postgres" not in services:
                reporter.add("PF-DB-CONNECT", "Connect to PostgreSQL", "Preflight", "BLOCKED",
                             "Connection succeeds using configured settings", note="Postgres service is not running or Docker status is unavailable; connection was not attempted.")
                reporter.add("PF-DB-READONLY", "Read-only transaction enforced", "Preflight", "BLOCKED",
                             "transaction_read_only=on", note="No database connection")
            else:
                conn = open_readonly_connection(reporter)
        else:
            conn = open_readonly_connection(reporter)

        smoke_ok = False
        dim_smoke: dict[str, bool] = {}
        if args.suite in ("smoke", "deep", "all"):
            smoke_ok, dim_smoke = run_smoke(reporter, conn, args.scope)
        if args.suite in ("deep", "all"):
            run_deep(reporter, conn, args.scope, smoke_ok, dim_smoke, args.include_large_scans)
        if conn is not None:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

    json_path, md_path = reporter.save()
    print(f"Suite: {reporter.suite}; scope: {reporter.scope}; overall: {reporter.overall()}")
    print("Counts: " + ", ".join(f"{key}={value}" for key, value in reporter.counts().items()))
    print(f"JSON: {json_path.relative_to(ROOT)}")
    print(f"Markdown: {md_path.relative_to(ROOT)}")
    return 1 if reporter.counts()["FAIL"] else (2 if reporter.counts()["BLOCKED"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
