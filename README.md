# NYC Yellow Taxi Data Warehouse

Kho dữ liệu và dashboard cho **NYC Yellow Taxi Trip Records 2024–2025** (24 file Parquet, khoảng 90 triệu chuyến đi). Dữ liệu đi qua một pipeline ELT chạy theo lịch: Mage nạp file nguồn vào DuckDB, dbt dựng Staging, Dimension/Fact (Star Schema) và OLAP mart, cuối cùng Power BI đọc mart đã xuất ra Parquet.

Tình trạng chi tiết và nhật ký thay đổi: [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Kiến trúc

```text
TLC Parquet (theo tháng) + Taxi Zone Lookup (CSV)
        │  Mage: tải file, kiểm tra schema, nạp mỗi file trong một transaction
        ▼
DuckDB  raw.yellow_tripdata, raw.taxi_zone_lookup, control.etl_control
        │  dbt (dbt-duckdb)
        ├─► stage.*        view: đặt tên, cột dẫn xuất, cờ chất lượng is_*
        ├─► snapshots.*    SCD Type 2 cho Taxi Zone
        ├─► dds.dim* (8) + dds.facttaxitrip      Star Schema, Fact incremental
        └─► olap.mart_* (5)                       mart tổng hợp cho báo cáo
        │  export_bi.py
        ▼
data/bi/*.parquet  ──►  Power BI (dashboard 7 trang)
```

Toàn bộ chuỗi trên là pipeline Mage `nyc_taxi_e2e`, chạy tự động 03:00 ngày 2 hằng tháng (giờ VN), có retry, timeout và cảnh báo khi lỗi.

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Orchestration, ingestion | Mage 0.9.79 (Docker) | Pipeline nạp dữ liệu và pipeline end-to-end theo lịch |
| Kho dữ liệu | DuckDB 1.5 (một file `data/warehouse/nyc_taxi.duckdb`) | Lưu `raw`, `stage`, `dds`, `olap` |
| Transform, test | dbt-core 1.12 + dbt-duckdb 1.11 (venv riêng `/opt/dbt` trong container) | Staging, snapshot SCD2, Dimension/Fact, OLAP mart, 98 test |
| Kiểm tra chất lượng | `tests/run_quality_tests.py` (chỉ đọc) | Đối chiếu xuyên tầng `raw → stage → dds → olap` |
| Báo cáo | Power BI Desktop | Đọc Parquet do pipeline xuất; template `.pbit` trong repo |
| CI | GitHub Actions | Cú pháp Python, `docker compose config`, `dbt parse` |

## Kết quả

| Chỉ số | Giá trị |
|---|---|
| Dòng `raw` (24 tháng) | 89.892.322 |
| Dòng Fact hợp lệ | 85.745.246 (95,39%) |
| Khóa Unknown (`-1`) trong Fact | 0 |
| `dbt build` | 98/98 PASS |
| Runner QA `full` | 53 PASS, 0 FAIL |
| Pipeline `nyc_taxi_e2e` khi không có tháng mới | khoảng 140 giây |

## Yêu cầu

- Windows với PowerShell, Git, Docker Desktop.
- RAM từ 12 GB (container Mage giới hạn 6 GB).
- Ổ đĩa: Parquet nguồn khoảng 1,5 GB; file DuckDB vài GB (DuckDB không tự thu hồi chỗ của dòng đã xóa khi nạp lại, xem [ingestion.md](docs/guides/ingestion.md#lưu-ý)).
- Power BI Desktop để mở dashboard.

Không cần cài Python, dbt hay DuckDB trên máy: mọi thứ chạy trong container.

## Bắt đầu nhanh

```powershell
git clone https://github.com/thinhdao-77/NYC_TAXI_DataPipeline.git
Set-Location NYC_TAXI_DataPipeline

.\tasks.ps1 up          # build image, khởi động Mage (http://localhost:6789)
.\tasks.ps1 e2e         # nạp 24 tháng -> dbt build -> QA -> xuất Parquet cho Power BI
.\tasks.ps1 status      # lần chạy thành công gần nhất, cảnh báo gần đây
```

Lần chạy đầu tải 24 file Parquet từ TLC và build Fact từ đầu, nên lâu hơn nhiều so với các lượt sau. `.env` không bắt buộc: mọi biến (`DUCKDB_*`, `RAW_DATA_DIR`) có mặc định trong `docker-compose.yml`. Muốn nhận cảnh báo qua Slack/Discord/Teams thì sao chép `.env.example` thành `.env` và đặt `ALERT_WEBHOOK_URL`.

Sau đó mở `powerbi/dashboard/NYC_Taxi_Dashboard.pbit`, nhập `RepoFolder` là thư mục gốc repo. Chi tiết: [docs/guides/powerbi.md](docs/guides/powerbi.md).

## Lệnh thường dùng

| Lệnh | Việc làm |
|---|---|
| `.\tasks.ps1 help` | Danh sách đầy đủ |
| `.\tasks.ps1 up` / `down` / `logs` | Quản lý container |
| `.\tasks.ps1 e2e ['{"file_name": "..."}']` | Pipeline end-to-end qua scheduler Mage (có retry, cảnh báo) |
| `.\tasks.ps1 ingest-zones`, `.\tasks.ps1 ingest [file \| ALL \| JSON]` | Chỉ nạp dữ liệu vào `raw` |
| `.\tasks.ps1 dbt-build [selector]` | `dbt build` trong container, vd `dbt-build fact_taxi_trips` |
| `.\tasks.ps1 qa [smoke\|deep\|all\|full]` | Runner QA chỉ đọc |
| `.\tasks.ps1 export-bi` | Xuất OLAP mart + Dimension ra `data/bi/*.parquet` |
| `.\tasks.ps1 sql "<câu SQL>"` | Truy vấn DuckDB chỉ đọc |
| `.\tasks.ps1 profile <file.sql>` | Chạy truy vấn profiling trong `sql/profiling/` |

DuckDB chỉ cho một tiến trình ghi: không chạy pipeline Mage và `dbt build` cùng lúc, đóng Power BI/DBeaver nếu chúng đang mở file `.duckdb`.

## Tài liệu

| Bước | Hướng dẫn |
|---|---|
| Nạp dữ liệu nguồn vào `raw` | [docs/guides/ingestion.md](docs/guides/ingestion.md) |
| Staging, cờ chất lượng, profiling | [docs/guides/staging.md](docs/guides/staging.md) |
| Dimension (gồm SCD2 cho Location) | [docs/guides/dimension.md](docs/guides/dimension.md) |
| Fact | [docs/guides/fact.md](docs/guides/fact.md) |
| OLAP mart | [docs/guides/olap.md](docs/guides/olap.md) |
| Kiểm thử (dbt test, runner QA) | [docs/guides/testing.md](docs/guides/testing.md) |
| Pipeline end-to-end, lịch, cảnh báo | [docs/guides/pipeline.md](docs/guides/pipeline.md) |
| Power BI | [docs/guides/powerbi.md](docs/guides/powerbi.md) |
| Mô hình dữ liệu (business event, Star Schema, câu hỏi phân tích) | [docs/data_modeling/modeling.pdf](docs/data_modeling/modeling.pdf) |

## Cấu trúc repository

```text
.
├── .github/workflows/        # ci.yml (kiểm tra khi push), auto-pr.yml (tự mở PR vào main)
├── Dockerfile, docker-compose.yml, requirements.txt, requirements-dbt.txt
├── tasks.ps1                 # lệnh thường dùng
├── data/
│   ├── download_raw.ps1      # tải trước Parquet (tùy chọn, pipeline tự tải)
│   ├── reference/            # Taxi Zone Lookup, ranh giới khu vực
│   ├── raw/, warehouse/, bi/ # Parquet nguồn, file DuckDB, Parquet cho Power BI (không commit)
├── mage/                     # pipelines ingest_zone_lookup, ingest_yellow_trips, nyc_taxi_e2e; custom/, callbacks/, utils/
├── dbt/                      # models/{staging,dds,olap_marts}, snapshots/, macros/, tests/
├── sql/
│   ├── ddl/                  # DDL raw/control (block nạp tự chạy)
│   └── profiling/            # truy vấn đo lỗi dữ liệu nguồn
├── tests/run_quality_tests.py
├── powerbi/                  # scripts/, queries/ (Power Query), dax/, map_shapes/, theme/, dashboard/*.pbit
└── docs/                     # PROJECT_STATUS.md, guides/, data_modeling/, test_plans_and_logs/
```

Không commit: `data/raw`, `data/warehouse`, `data/bi`, `.env`, file `.pbix` (khoảng 125 MB, có dữ liệu).

## Quy trình Git

Repo cá nhân, một người phát triển: tạo nhánh từ `main` mới nhất → commit → push → `auto-pr.yml` tự mở Pull Request vào `main` → CI chạy theo `push` → merge. Repo tự xóa nhánh remote sau khi merge.

```powershell
git checkout main; git pull --ff-only
git checkout -b feat/<pham-vi>
git add <file>; git commit -m "feat(<scope>): <mô tả>"
git push -u origin feat/<pham-vi>

# sau khi merge
git checkout main; git pull --ff-only; .\tasks.ps1 prune-branches
```

Quy ước commit: `<type>(<scope>): <mô tả ngắn>`, type thường dùng `feat`, `fix`, `docs`, `test`, `chore`, `refactor`; scope như `mage`, `dbt`, `fact`, `olap`, `powerbi`, `pipeline`, `docs`.
