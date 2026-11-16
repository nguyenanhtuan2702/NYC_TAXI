# Tình trạng dự án NYC Yellow Taxi Data Warehouse

> Cập nhật: 16/11/2026 — nhánh `refactor/project-structure` của fork `thinhdao-77/NYC_TAXI_DataPipeline`.
> File này được cập nhật cùng mỗi thay đổi. Lịch sử ở [mục 7](#7-nhật-ký-thay-đổi).

## 1. Mục tiêu

Xây dựng quy trình ELT và kho dữ liệu cho **NYC Yellow Taxi Trip Records 2024–2025**:
Parquet nguồn → PostgreSQL Staging (Mage) → Dimension/Fact (dbt) → OLAP mart → Power BI.

## 2. Mức độ hoàn thành

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Hạ tầng Docker (Mage + DuckDB) | **Đã chuyển sang DuckDB, đã chạy thử** | Chỉ còn service `mage` (Mage 0.9.79 + duckdb 1.5.6; dbt 1.12 trong venv `/opt/dbt`); file DuckDB ở `data/warehouse/nyc_taxi.duckdb`. Xem [mục 8](#8-chuyển-sang-duckdb) |
| DDL Staging | Hoàn thành | `sql/ddl/`: schema `stage`, `control`; bảng `stg_yellow_taxi_trips`, `stg_taxi_zone_lookup`, `etl_control` |
| Nạp Taxi Zone Lookup | Hoàn thành | Pipeline Mage `ingest_zone_lookup` (265 dòng) |
| Nạp Yellow Taxi Parquet | Hoàn thành | Pipeline `ingest_trips_to_postgres`: tự tải file, retry, batch, LSET, self-healing, log theo file |
| Profiling dữ liệu nguồn | Hoàn thành | `sql/profiling/02..11` + `inspect_parquet.py` |
| dbt project | Hoàn thành (cấu hình) | `dbt_project.yml`, `profiles.yml` (đọc `.env`), `sources.yml`; `dbt parse` OK trên dbt-core 1.12.7 |
| Dimension (8 bảng) | Có model dbt, **chưa chạy trên DB** | `dbt/models/dds/dimensions/`; SK ổn định, dòng Unknown `-1`; 30 test schema + 1 test Unknown member |
| Fact `facttaxitrip` | Có model dbt, **chưa chạy trên DB** | `dbt/models/dds/facts/fact_taxi_trips.sql`, incremental theo `batch_id`, 16 test |
| SQL thủ công DDS | Lưu để tham khảo | `sql/warehouse/01..05` (Dimension idempotent + Fact + verify) |
| Bộ kiểm thử QA (Stage/Dimension) | Hoàn thành | `tests/run_quality_tests.py`, chỉ đọc, suite `smoke`/`deep`/`all` |
| Test plan + log | Hoàn thành | `docs/02_test_plans_and_logs/` (giữ 1 lần chạy mẫu `run_20261026T034420Z`) |
| CI | Hoàn thành | `.github/workflows/ci.yml`: cú pháp Python, `docker compose config`, `dbt parse` |
| Lệnh tiện ích | Hoàn thành | `tasks.ps1` (up/down/psql/profile/dbt-*/qa) |
| Báo cáo thành phần | Một phần | `docs/03_reports/sections/` (Vân, Khoa) |
| Data modeling docs | Một phần | Có `docs/01_data_modeling/modeling.pdf` (chưa commit) |
| OLAP mart | **Chưa có** | `dbt/models/olap_marts/{basic,advanced}` rỗng |
| Pipeline ELT end-to-end | **Chưa có** | Cần pipeline Mage: ingest → `dbt build` |
| Power BI | **Chưa có** | `powerbi/` rỗng |

## 3. Chi tiết phần đã làm

### 3.1 Ingestion → Staging
- `stage.stg_yellow_taxi_trips` giữ nguyên dữ liệu nguồn + cột kiểm toán (`source_file_name`, `source_row_number`, `batch_id`, `load_datetime`); `cbd_congestion_fee` chỉ có từ 2025-01.
- Lần kiểm thử 26/10: ~9,56 triệu dòng (mới nạp một phần), zone lookup 265 dòng.
- Đầy đủ: ~1,5 GB Parquet, ~20 GB bảng staging.

### 3.2 Dimension (dbt)

| Model | Bảng | SK | Nguồn |
|---|---|---|---|
| `dim_date` | `dds.dimdate` | `YYYYMMDD` | sinh 2024-01-01..2025-12-31 |
| `dim_time` | `dds.dimtime` | `hour*100+minute` | sinh 24×60 |
| `dim_location` | `dds.dimlocation` | = `LocationID` | zone lookup |
| `dim_vendor` | `dds.dimvendor` | = `VendorID` | trips; mã ngoài 1/2 → Unknown |
| `dim_payment_type` | `dds.dimpaymenttype` | = `PaymentTypeID` | trips; mã 0 → Unknown |
| `dim_rate_code` | `dds.dimratecode` | = `RateCodeID` | trips; NULL → 99 Unknown |
| `dim_passenger_group` | `dds.dimpassengergroup` | 1..3 | tĩnh (LARGE tới 9999) |
| `dim_distance_group` | `dds.dimdistancegroup` | 1..3 | tĩnh, `NUMERIC(10,4)` |

Logic nghiệp vụ giữ nguyên bản SQL đã sửa trong `feat/fact-thinh`. Khác biệt: SK không còn là `SERIAL` mà sinh từ khóa tự nhiên, để Fact incremental không bị lệch khóa khi Dimension build lại. Tên bảng/cột vật lý giữ nguyên, nên runner QA vẫn dùng được.

### 3.3 Fact (dbt)
Grain: một chuyến đi hợp lệ. Lọc `dropoff > pickup`, pickup trong 2024–2025, `fare/total/distance >= 0`. Tra khóa bằng `LEFT JOIN` + `COALESCE(sk, -1)`. Nạp gia tăng theo `batch_id > max(batchid)`.

### 3.4 QA
Lần chạy 26/10 (`run_20261026T034420Z`): 19 PASS, 8 FAIL, 14 BLOCKED. 8 FAIL đều do bảng Dimension chưa tồn tại trong DB lúc test.

## 4. Vấn đề và rủi ro còn mở

1. **Chưa chạy dbt trên database thật** (Docker chưa bật khi refactor). Cần `.\tasks.ps1 dbt-build` rồi chạy lại QA.
2. Hai cách build DDS cùng tồn tại (dbt và `sql/warehouse/`). Không được trộn: dbt build lại Dimension sẽ xóa khóa ngoại do `03_create_fact.sql` tạo. Nên chọn dbt làm chuẩn và cân nhắc bỏ bản SQL khi dbt đã ổn.
3. Fact dbt không có `TripSK` (bản SQL có `BIGSERIAL`). Cần thống nhất nếu Power BI cần khóa chuyến đi.
4. Dimension đọc `SELECT DISTINCT` từ bảng trips ~20 GB (3 lần: vendor, payment, ratecode); có thể chậm khi đủ dữ liệu.
5. Fact incremental dựa vào `batch_id` tăng dần: nếu nạp lại một file cũ với `batch_id` mới, chuyến đi sẽ bị trùng trong Fact.
6. Mage lưu cache chạy theo uuid pipeline. Sau khi đổi `letter_01_ingest_source_to_postgres` → `ingest_zone_lookup`, lịch sử chạy cũ trên Mage UI sẽ không hiện dưới tên mới. Pipeline `ingest_trips_to_postgres` giữ nguyên tên vì `control.etl_control.pipeline_name` dùng tên này cho LSET.
7. `data/reference/taxi_zones.zip` (nhị phân) vẫn nằm trong git.

## 5. Cấu trúc thư mục hiện tại

```text
.
├── .github/workflows/ci.yml
├── data/{raw,reference,sample}, download_raw.ps1
├── dbt/                      # transform chính: sources → dds (dims, facts) → olap_marts
├── mage/                     # ingestion: pipelines ingest_zone_lookup, ingest_trips_to_postgres
├── sql/
│   ├── ddl/                  # DDL Staging (mount vào /docker-entrypoint-initdb.d)
│   ├── profiling/            # truy vấn kiểm tra dữ liệu nguồn
│   └── warehouse/            # SQL thủ công Dimension/Fact (tham khảo)
├── tests/                    # runner QA chỉ đọc
├── powerbi/
├── docs/
│   ├── PROJECT_STATUS.md     # file này
│   ├── guides/               # staging, dimension, dimension_handover, fact, testing
│   ├── 01_data_modeling/
│   ├── 02_test_plans_and_logs/
│   └── 03_reports/
├── docker-compose.yml, Dockerfile, requirements.txt, tasks.ps1, .env.example, README.md
```

## 6. Việc nên làm tiếp

1. Bật Docker, tạo `.env`, `docker compose up -d --build` (cần build lại image vì Dockerfile đổi), chạy `.\tasks.ps1 dbt-build` và `.\tasks.ps1 qa all`.
2. Quyết định giữ hay bỏ `sql/warehouse/`; thống nhất `TripSK` cho Fact.
3. Commit `docs/01_data_modeling/modeling.pdf` (hoặc chuyển thành markdown/ERD) và bổ sung data dictionary.
4. Xây OLAP mart (`dbt/models/olap_marts/`).
5. Pipeline Mage end-to-end: ingest → `dbt build`.
6. Dashboard Power BI.

## 7. Nhật ký thay đổi

### 16/11/2026 — DuckDB bước 1: Docker Compose
- `docker-compose.yml`: bỏ service `postgres` và volume `pgdata`; đặt tên project `nyc-taxi`; Mage nâng giới hạn RAM lên 6 GB (DuckDB chạy trong tiến trình Mage/dbt); thêm biến `DUCKDB_PATH`, `DUCKDB_MEMORY_LIMIT`, `DUCKDB_THREADS`, `DUCKDB_TEMP_DIR`, `RAW_DATA_DIR`, đều có giá trị mặc định nên `.env` không còn bắt buộc.
- `.env.example`: thay biến PostgreSQL bằng biến DuckDB.
- Thêm `data/warehouse/` (chứa file `.duckdb`, không commit); `.gitignore` bỏ `pgdata/`, thêm `*.duckdb.wal`, `data/warehouse/*`.
- **Image và phụ thuộc** (sửa sau 2 lần build/chạy lỗi):
  - Lỗi 1: `duckdb~=2.0.0` không cài được vì image Mage dùng Python 3.10, duckdb 2.x cần >= 3.11. Chuyển sang `duckdb~=1.5.6`.
  - Lỗi 2: container khởi động lỗi `TypeError: Secondary flag is not valid for non-boolean flag` vì `dbt-core` 1.12 kéo `click>=8.3` (và `protobuf>=6`), phá `typer 0.9` / `click 8.1.8` mà CLI Mage 0.9.79 dùng.
  - Cách sửa: `Dockerfile` ghim image theo digest (`mageai/mageai:latest@sha256:4409…`, mage-ai 0.9.79); dbt cài trong virtualenv riêng `/opt/dbt` (symlink `/usr/local/bin/dbt`), không đụng môi trường Mage. Tách `requirements.txt` (môi trường Mage: chỉ `duckdb~=1.5.6`) và `requirements-dbt.txt` (`dbt-core~=1.12.0`, `dbt-duckdb~=1.11.1`, `dbt-postgres` tạm giữ đến bước 4, `duckdb~=1.5.6`). Mage và dbt dùng cùng duckdb 1.5.6 để đọc/ghi chung một file. CI cài cả hai file.
- `tasks.ps1`: bỏ `psql`, thêm `shell` (bash trong Mage) và `sql "<câu SQL>"` (truy vấn DuckDB chỉ đọc); `profile` chạy trên DuckDB; pipe dùng UTF-8.
- **Kiểm tra trên Docker (đạt):** image build OK; trong môi trường Mage `click 8.1.8`, `typer 0.9.0`, `protobuf 4.25.8`, `duckdb 1.5.6`, `pip check` không xung đột, `mage` CLI chạy; `dbt --version` = 1.12.7 với plugin duckdb 1.11.1 và postgres 1.11.0; container `Up`, Mage UI HTTP 200 sau ~12 s; DuckDB nhận `memory_limit` 3.7 GiB, 4 threads; `.\tasks.ps1 sql` trả kết quả đúng kể cả tiếng Việt.
- **Đo I/O** (20 triệu dòng, ghi + checkpoint / đọc tổng hợp): bind mount ổ D: 14,5 s / 1,6 s; filesystem trong container 15,4 s / 2,2 s. Không chậm hơn, nên **giữ file DuckDB trên bind mount** (`data/warehouse/`) để Power BI mở trực tiếp.

### 16/11/2026 — Tái cấu trúc thư mục (nhánh `refactor/project-structure`)
- Merge `upstream/feat/fact-thinh`: dbt project, model Fact, SQL Fact, bản sửa Dimension idempotent.
- **Mục 1:** chuyển 8 Dimension sang dbt (`dbt/models/dds/dimensions/` + `schema.yml` + test Unknown member); Fact dùng `ref()` thay vì `source('dds', ...)`; `sources.yml` chỉ còn `stage`; `profiles.yml` bỏ mật khẩu mặc định, đọc `POSTGRES_PORT`; test `relationships` chuyển sang cú pháp `arguments:`. `warehouse/*.sql` → `sql/warehouse/`; bỏ luật `.gitignore` riêng cho `warehouse/`.
- **Mục 2:** pipeline `letter_01_ingest_source_to_postgres` → `ingest_zone_lookup`; xóa 2 thư mục pipeline rỗng.
- **Mục 3:** `staging/init_sql` → `sql/ddl` (cập nhật mount trong `docker-compose.yml`), `staging/pg_checks` → `sql/profiling`; README rải rác → `docs/guides/` (`staging.md`, `dimension.md`, `dimension_handover.md`, `fact.md`, `testing.md`); cập nhật đường dẫn trong README, guides, test plan và `tests/run_quality_tests.py`.
- **Mục 4:** `.gitignore` bỏ qua `docs/02_test_plans_and_logs/runs/*`, chỉ giữ `run_20261026T034420Z`; 12 file log khác bỏ khỏi git (file local vẫn còn).
- **Mục 5:** thêm `requirements.txt` (dbt-core 1.12, dbt-postgres 1.11), `Dockerfile` cài từ file này, `tasks.ps1`, CI GitHub Actions.
- Kiểm tra: `dbt parse` sạch trên dbt-core 1.12.7; `python -m compileall` OK; `tasks.ps1` parse OK; runner QA `PF-REPO-01` PASS với đường dẫn mới. Chưa chạy dbt trên DB.

### 16/11/2026 — Khởi tạo
- Fork repo, cấu hình remote `origin` (fork) và `upstream` (repo gốc, chặn push). Viết bản tóm tắt đầu tiên.

## 8. Chuyển sang DuckDB

Quyết định ngày 16/11/2026: thay PostgreSQL bằng DuckDB làm kho dữ liệu, làm lần lượt theo thứ tự pipeline. Fork sẽ khác repo nhóm (vẫn dùng PostgreSQL) ở các phần ingestion, staging, test.

| Bước | Phạm vi | Trạng thái |
|---|---|---|
| 1. Hạ tầng | `docker-compose.yml`, `Dockerfile`, `.env.example`, `requirements*.txt`, `tasks.ps1` | **Xong, đã chạy thử trên Docker** |
| 2. Source → Ingestion | Mage: tải Parquet + Zone Lookup, log nạp (`etl_control`) và LSET trên DuckDB; `mage/io_config.yaml` | Chưa làm |
| 3. Staging | Schema `stage` trong DuckDB (view/bảng trên Parquet), chuyển `sql/ddl`, `sql/profiling` sang cú pháp DuckDB | Chưa làm |
| 4. ETL/ELT | dbt-duckdb: `profiles.yml`, sửa hàm riêng PostgreSQL trong model (`to_char`, `generate_series`, ...) | Chưa làm |
| 5. Data warehouse | DDS (Dimension, Fact) + OLAP mart; test dbt; runner QA chuyển sang thư viện `duckdb` | Chưa làm |
| 6. Power BI | Kết nối DuckDB (ODBC, chế độ Import) hoặc đọc mart xuất ra Parquet | Chưa làm |

**Tạm thời không chạy được cho tới bước tương ứng:** pipeline Mage hiện tại (vẫn ghi vào PostgreSQL), `mage/io_config.yaml`, các truy vấn `sql/ddl` và `sql/profiling`, `dbt/profiles.yml` (adapter postgres), runner QA (`tests/run_quality_tests.py` gọi `psql` trong container `postgres`), và hướng dẫn PostgreSQL trong README và `docs/guides/`.

**Lưu ý vận hành DuckDB**
- Chỉ một tiến trình được ghi vào file. Không chạy đồng thời pipeline Mage và `dbt build`; đóng Power BI/DBeaver trước khi ghi.
- File `.duckdb` nằm trên bind mount (ổ D: của Windows) để Power BI mở trực tiếp được. Đã đo: không chậm hơn filesystem trong container (xem nhật ký bước 1).
- dbt chạy từ venv `/opt/dbt` trong container (`dbt` hoặc `.\tasks.ps1 dbt-*`). Không `pip install` gói dbt vào môi trường Mage: sẽ làm hỏng CLI Mage.
