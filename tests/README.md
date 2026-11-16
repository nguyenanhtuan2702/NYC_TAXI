# Read-only ETL QA runner

The repository uses PostgreSQL 17, Mage and Docker Compose. The task prompt mentioned SQL Server; this runner follows the PostgreSQL implementation actually configured in the repository.

## Run

Run from the repository root while the PostgreSQL Compose service is healthy:

```powershell
# One common command: Preflight -> Stage Smoke -> each Dimension Smoke
python tests\run_quality_tests.py --suite smoke

# Run one scope only
python tests\run_quality_tests.py --suite smoke --scope stage
python tests\run_quality_tests.py --suite smoke --scope dimension

# Deep tests rerun Smoke first and gate dependent checks
python tests\run_quality_tests.py --suite deep
python tests\run_quality_tests.py --suite all

# Include full scans over the trip table
python tests\run_quality_tests.py --suite deep --include-large-scans
```

If local Python is unavailable, use Mage's existing Python runtime:

```powershell
docker compose exec -T mage python /home/src/tests/run_quality_tests.py --suite smoke
```

Each invocation writes Markdown and JSON under `docs/02_test_plans_and_logs/runs/`. Statuses remain distinct: `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, and `NOT APPLICABLE`.

## Safety and limits

- Every database query runs in a read-only transaction and is rolled back. The runner never invokes Mage ETL or a DDL/DML script.
- Dimension creation contains `DROP TABLE ... CASCADE`; its load script appends with `INSERT`. Idempotency checks require a disposable database and are marked `BLOCKED` until one is configured.
- `--include-large-scans` runs aggregations, duplicate checks, and reconciliation against the trip table. These queries do not write data, but may use substantial database resources.
- Stage anomaly metrics have no business thresholds in the repository; they are reported as measurements, not silently treated as pass/fail.
- Negative fixtures require an isolated PostgreSQL database. No fixture is inserted into the operational database.
- Fact tests remain `BLOCKED` because there is no Fact implementation in tracked files.

See [the test plan](../docs/02_test_plans_and_logs/test-plan.md) for expectations and current findings.
