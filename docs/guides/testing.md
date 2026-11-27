# Kiểm thử: dbt test và runner QA chỉ đọc

Dự án có hai lớp kiểm thử bổ sung cho nhau:

| Lớp | Chạy bằng | Khi nào | Đặc điểm |
|---|---|---|---|
| **dbt test** | `.\tasks.ps1 dbt-build` / `dbt-test` | Mỗi lần build model | Gắn với từng model (schema test + singular test trong `dbt/tests/`); build lỗi thì dừng |
| **Runner QA** | `.\tasks.ps1 qa [suite]` | Sau khi pipeline chạy xong, trước khi dùng dữ liệu (Power BI) | Độc lập với dbt, chỉ đọc, kiểm tra xuyên tầng `raw → stage → dds → olap`, xuất báo cáo JSON + Markdown |

## Runner QA (`tests/run_quality_tests.py`)

Chạy trong container Mage (có sẵn thư viện `duckdb` 1.5.x, cùng phiên bản với file dữ liệu):

```powershell
.\tasks.ps1 qa                # smoke (mặc định)
.\tasks.ps1 qa deep           # smoke + deep, bỏ qua các kiểm tra quét lớn (NOT RUN)
.\tasks.ps1 qa full           # all + --include-large-scans: đầy đủ, ~30 s trên 24 tháng

# Lệnh gốc, có thêm lựa chọn phạm vi (raw | stage | dimension | fact | olap)
docker compose exec -T mage python /home/src/tests/run_quality_tests.py --suite deep --scope fact
```

Mỗi lượt chạy ghi `docs/test_plans_and_logs/runs/run_<thời điểm UTC>.json` và `.md` (không commit, trừ bản mẫu). Mã thoát: `0` không có FAIL/BLOCKED, `1` có FAIL, `2` có BLOCKED. Trạng thái: `PASS`, `FAIL`, `BLOCKED` (không chạy được do điều kiện trước chưa đạt), `NOT RUN` (cần `--include-large-scans`), `NOT APPLICABLE`.

**An toàn:** database mở bằng `duckdb.connect(read_only=True)`; preflight chứng minh bằng cách thử một lệnh `CREATE TABLE` và yêu cầu nó bị từ chối. Runner không gọi Mage, dbt, DDL hay DML. DuckDB chỉ cho một tiến trình ghi: nếu pipeline Mage hoặc dbt đang chạy, preflight báo `BLOCKED`.

Đổi file database cần kiểm tra bằng biến môi trường `DUCKDB_PATH` (ví dụ một bản sao thử nghiệm).

### Các kiểm tra

| Mã | Tầng | Kiểm tra | Quét lớn |
|---|---|---|:---:|
| `PF-REPO-01` | Preflight | Đủ file DDL, pipeline Mage, project dbt, Zone CSV | |
| `PF-ENGINE-01` | Preflight | `docker-compose.yml` cấu hình `DUCKDB_PATH`, không có service database riêng | |
| `PF-COMPOSE-01` | Preflight | `docker compose config` hợp lệ (chỉ khi chạy trên host) | |
| `PF-DB-DRIVER/CONNECT/READONLY` | Preflight | duckdb 1.5.x; mở được file; lệnh ghi bị từ chối | |
| `SM-<bảng>` | Smoke | 12 bảng/view (`raw`, `control`, `stage`, `snapshots`, `dds.facttaxitrip`, 5 mart) tồn tại, có dữ liệu | |
| `SM-Dim*` | Smoke | 8 Dimension đủ cột, đúng một dòng Unknown (-1) | |
| `RAW-SCH-01/02` | Deep raw | Hợp đồng schema `raw.*` khớp `sql/ddl/02_create_raw.sql` | |
| `RAW-CMP-01` | Deep raw | Cột kiểm toán `source_file_name`, `load_datetime` NOT NULL | |
| `RAW-REC-01/02` | Deep raw | Lượt nạp SUCCESS tự khớp; lượt nạp cuối của mỗi file không FAILED | |
| `RAW-REC-03` | Deep raw | Số dòng raw theo file = `rows_loaded` của lượt nạp cuối | |
| `RAW-DUP-01` | Deep raw | `source_row_number` liên tục 1..N trong mỗi file (không trùng, không mất) | |
| `STG-REC-01` | Deep stage | Staging giữ đủ dòng của raw | |
| `STG-KEY-01` | Deep stage | `location_id` của Zone Lookup duy nhất, không NULL | |
| `STG-VAL-01` | Deep stage | Mọi cờ `is_*` không NULL; ghi nhận số dòng từng cờ | ✔ |
| `DIM-SCH-*` | Deep dimension | SK, khóa tự nhiên không NULL/không trùng; số dòng Dimension tĩnh | |
| `DIM-SCD-01/02` | Deep dimension | DimLocation SCD2: một bản hiện hành, các bản nối liền, đủ phiên bản của snapshot | |
| `DIM-MAP-02` | Deep dimension | Mã lạ mang nhãn Unknown | |
| `DIM-MAP-01` | Deep dimension | Mọi mã trong staging có trong Dimension | ✔ |
| `FACT-KEY-01` | Deep fact | Không có khóa -1 ở cả 11 khóa | |
| `FACT-VAL-01` | Deep fact | Measure tuân thủ quy tắc `is_valid_for_fact` | |
| `FACT-REC-01` | Deep fact | Mỗi file: số dòng và tổng `sourcerownumber` bằng staging hợp lệ | ✔ |
| `FACT-REF-01` | Deep fact | Không khóa mồ côi (anti join 11 Dimension) | ✔ |
| `OLAP-REC-01` | Deep olap | Tổng chuyến, hành khách, doanh thu của 5 mart (mart giờ: từng vai trò) khớp Fact | |
| `OLAP-KPI-01` | Deep olap | `mart_monthly_kpi` không trùng tháng, liên tục | |

Một tầng chỉ chạy deep khi các bảng của nó (và tầng phụ thuộc) đã qua smoke; nếu không, ghi `BLOCKED`.

### Kết quả 18/11/2026 (24 tháng, ~90 triệu dòng)

- `.\tasks.ps1 qa full`: **53 PASS, 0 FAIL, 1 NOT APPLICABLE** (`PF-COMPOSE-01` trong container), ~32 s. Kiểm tra lâu nhất: `STG-VAL-01` ~15 s.
- **Kiểm thử âm tính:** bản sao chỉ có 2 tháng, cố ý nạp trùng 10 dòng file 2024-01 và xóa 1 dòng file 2024-02 → `RAW-DUP-01` FAIL đúng 2 file, `RAW-REC-03` FAIL, mã thoát 1. (`RAW-CMP-01` cũng FAIL vì bảng thử tạo bằng `CREATE TABLE AS` không giữ ràng buộc NOT NULL: đúng hành vi.)
- Bản mẫu được commit: `docs/test_plans_and_logs/runs/run_20261118T115030Z.*`.

## dbt test

| Nhóm | Vị trí | Nội dung chính |
|---|---|---|
| Staging | `models/staging/schema.yml`, `tests/staging/` | NOT NULL kiểm toán, khóa Zone, `relationships` (warn), số dòng khớp raw, `source_row_number` liên tục |
| Dimension | `models/dds/dimensions/schema.yml`, `tests/dimensions/` | SK unique/not null, dòng Unknown, SCD2 hợp lệ (`assert_dim_location_scd2_valid`) |
| Fact | `models/dds/facts/schema.yml`, `tests/facts/` | NOT NULL, `relationships` 7 khóa, số dòng theo file khớp staging |
| OLAP | `models/olap_marts/schema.yml`, `tests/olap/` | NOT NULL, `accepted_values`, tháng KPI duy nhất, tổng mart khớp Fact |

`dbt build` toàn bộ (18/11/2026): 98/98 PASS, ~3 phút 12 giây (gồm build lại Fact từ đầu).
