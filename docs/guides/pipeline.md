# Pipeline end-to-end và lịch chạy (Mage)

Pipeline Mage `nyc_taxi_e2e` chạy toàn bộ luồng dữ liệu theo thứ tự, mỗi bước chỉ bắt đầu khi bước trước thành công:

| # | Block (`mage/`) | Việc làm | Ghi chú |
|---:|---|---|---|
| 1 | `data_loaders/load_zone_lookup.py` | Đọc `data/reference/taxi_zone_lookup.csv` | Dùng chung với pipeline `ingest_zone_lookup` |
| 2 | `data_exporters/export_zone_lookup.py` | Thay toàn bộ `raw.taxi_zone_lookup` | Full refresh; snapshot SCD2 ở bước 4 chỉ tạo phiên bản mới khi khu vực đổi |
| 3 | `data_exporters/load_trips_to_raw.py` | Nạp `raw.yellow_tripdata` cho các tháng 2024–2025 **chưa** SUCCESS, và nạp lại tháng đã SUCCESS nếu TLC đã phát hành lại file | Tháng không đổi in `[SKIP]`; file thiếu tự tải từ TLC; thiếu cột bắt buộc thì FAILED (xem mục "Bảo vệ dữ liệu nguồn") |
| 4 | `custom/run_dbt_build.py` | `dbt build`: snapshot, staging, Dimension, Fact, OLAP mart và mọi test dbt | Gọi `/opt/dbt/bin/dbt` bằng subprocess (dbt nằm trong venv riêng). Fact incremental: không có batch mới thì không nạp lại |
| 5 | `custom/run_quality_checks.py` | Runner QA chỉ đọc (`tests/run_quality_tests.py`) | Có FAIL thì **dừng**, không xuất dữ liệu sai cho Power BI; BLOCKED chỉ cảnh báo |
| 6 | `custom/export_powerbi.py` | Xuất mart + Dimension ra `data/bi/*.parquet` | Power BI: Home > Refresh |

Các bước chạy tuần tự trong một lượt, nên tại mỗi thời điểm chỉ một tiến trình mở file DuckDB để ghi.

**Vì sao bước 4 là block custom, không phải block dbt của Mage.** Block dbt của Mage chạy bản dbt cài sẵn trong môi trường Python của Mage. Trong image Mage 0.9.79 đó là dbt-core **1.8.7** + dbt-duckdb **1.8.4** (kiểm tra bằng `pip list` trong container). Project dùng dbt-core **1.12.7** + dbt-duckdb **1.11.1** trong venv `/opt/dbt`:
- **Snapshot không chạy được:** `dbt/snapshots/snap_taxi_zone_lookup.yml` khai báo snapshot bằng YAML (`relation:`, `hard_deletes:`), cú pháp chỉ có từ dbt 1.9. Với dbt 1.8, snapshot này (nguồn của `dim_location` SCD2) không chạy.
- **Không nâng được dbt trong Mage:** nâng dbt trong môi trường Mage lên 1.12 cần `click>=8.3`, làm hỏng CLI của Mage (`typer 0.9`, `click 8.1`). Đây là lý do dbt được tách ra venv riêng.
- **Hai phiên bản dùng chung một project:** chạy song song hai phiên bản dbt trên cùng `dbt/target` dễ làm hỏng `partial_parse` / `manifest.json`.

Đánh đổi: không có giao diện từng model dbt trong Mage (lineage, chạy lẻ một model). Log `dbt build` vẫn hiện đủ trong log block; chạy lẻ model thì dùng biến `dbt_select` hoặc `.\tasks.ps1 dbt-build <selector>`.

## Chạy tay

```powershell
.\tasks.ps1 up      # khởi động container (scheduler của Mage chạy cùng server)
.\tasks.ps1 e2e     # chạy một lượt qua scheduler (trigger manual_e2e), đợi đến khi xong; lỗi thì trả mã khác 0
.\tasks.ps1 status  # lần chạy thành công gần nhất, cảnh báo gần đây
```

`e2e` tạo một lượt chạy cho trigger API `manual_e2e`, rồi scheduler trong server Mage thực thi. Lượt chạy tay vì thế giống hệt lượt theo lịch: có retry, cảnh báo, timeout và hiện trong lịch sử trên giao diện Mage. Lệnh in trạng thái từng block và 25 dòng log cuối của block lỗi.

Biến của pipeline (đặt trong `metadata.yaml`, ghi đè khi chạy bằng JSON):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `file_name` | `ALL` | `ALL` = mọi tháng 2024–2025 chưa nạp hoặc nguồn đã đổi; hoặc một file, vd `yellow_tripdata_2025-03.parquet` (nạp lại file đó) |
| `check_source_updates` | `true` | So ETag/kích thước của file trên TLC (HEAD) với phiên bản đã nạp; khác thì tải và nạp lại |
| `force_download` | `false` | `true` = bỏ file Parquet local, tải lại từ TLC trước khi nạp (dùng với một `file_name`) |
| `qa_suite` | `all` | `smoke`, `deep` hoặc `all` |
| `qa_large_scans` | `false` | `true` = thêm kiểm tra quét toàn bộ staging/Fact (chậm hơn) |
| `dbt_select` | (trống) | Giới hạn `dbt build`, vd `olap_marts` |

```powershell
# Nạp lại một tháng rồi build, QA, xuất lại
.\tasks.ps1 e2e '{"file_name": "yellow_tripdata_2025-03.parquet"}'
```

Trên giao diện Mage (<http://localhost:6789>) > Pipelines > `nyc_taxi_e2e` xem được đồ thị block, log từng block và lịch sử các lượt chạy.

## Lịch chạy

Trigger `monthly_e2e` lưu trong `mage/pipelines/nyc_taxi_e2e/triggers.yaml` (Mage tự đọc khi server khởi động và có thể viết lại file theo định dạng của nó):

| Thuộc tính | Giá trị | Giải thích |
|---|---|---|
| `schedule_interval` | `0 20 1 * *` | Cron theo **UTC**: 20:00 UTC ngày 1 = **03:00 sáng ngày 2** giờ Việt Nam. Hằng tháng vì TLC phát hành dữ liệu theo tháng |
| `skip_if_previous_running` | `true` | Không chạy chồng hai lượt (DuckDB chỉ cho một tiến trình ghi) |
| `timeout` / `timeout_status` | `7200` / `failed` | Lượt chạy quá 2 giờ (bình thường khoảng 2 phút) bị đánh dấu FAILED |
| `variables` | như bảng trên | |

**Retry:** các block `export_zone_lookup`, `load_trips_to_raw`, `run_dbt_build`, `export_powerbi` thử lại tối đa 2 lần, chờ từ 60 giây và tăng dần, tổng chờ không quá 10 phút (`retry_config` trong `metadata.yaml`). Mục đích là vượt qua lỗi tạm thời như mất mạng hay file DuckDB đang bị khóa. Block QA không retry vì kết quả của nó cố định. Retry, callback cảnh báo và timeout chỉ có trong lượt chạy qua scheduler: lượt theo lịch và `.\tasks.ps1 e2e` (trigger API `manual_e2e`, tạo bằng `mage/utils/trigger_run.py`). `.\tasks.ps1 e2e-direct` chạy thẳng bằng `mage run`: mỗi block một lần, không gửi cảnh báo.

## Cảnh báo và theo dõi

- **Khi một block lỗi** (sau khi đã hết số lần retry), callback `mage/callbacks/notify_pipeline_failure.py` gọi `mage/utils/alerts.py`:
  - luôn ghi một dòng JSON vào `data/warehouse/alerts/pipeline_alerts.jsonl`. Ghi ra file chứ không ghi vào DuckDB, vì lỗi có thể chính là file DuckDB đang bị khóa;
  - nếu đặt `ALERT_WEBHOOK_URL` trong `.env` (incoming webhook của Slack, Discord hoặc Teams) thì gửi thêm tin nhắn. Cùng một block chỉ gửi một lần trong 60 phút.

  Đặt webhook rồi chạy `.\tasks.ps1 up` để container nhận biến mới.
- **`.\tasks.ps1 status`** (chạy trên máy host, không cần container) hiện:
  - lần chạy thành công gần nhất, lấy theo thời điểm xuất Parquet trong `data/bi/_manifest.json`. Quá 35 ngày thì cảnh báo, nghĩa là lượt theo lịch đã bị lỡ, ví dụ máy tắt, hoặc đã lỗi;
  - 5 cảnh báo lỗi gần nhất;
  - trạng thái container.
- **Power BI:** truy vấn `powerbi/queries/DataFreshness.pq` đọc thời điểm xuất để hiện card "Data as of" (xem `powerbi.md`).

## Bảo vệ dữ liệu nguồn

- **Schema drift:** file nguồn thiếu một cột bắt buộc, ví dụ TLC đổi tên `tip_amount`, thì lần nạp file đó **FAILED** kèm danh sách cột hiện có. Trước đây cột thiếu bị nạp thành NULL, rồi Fact `COALESCE` thành 0 mà không ai biết. Chỉ `cbd_congestion_fee` được phép thiếu ở các file trước 2025-01. Cột lạ chỉ in `[SCHEMA WARN]`, không nạp.
- **TLC phát hành lại file:** mỗi lượt `ALL`, với file đã SUCCESS, pipeline gửi `HEAD` lên TLC rồi so ETag (hoặc kích thước) với `control.source_file_meta`. Khác nhau thì in `[SOURCE UPDATED]`, tải lại và nạp lại. Fact delete+insert theo file nên không bị trùng.
  - Các file nạp trước khi có cơ chế này được ghi mốc ở lượt đầu: kích thước file local bằng Content-Length thì coi là cùng phiên bản.
  - Mất mạng thì chỉ cảnh báo `[SOURCE CHECK WARN]` và bỏ qua bước so sánh.
- **Fact dọn file đã bị xóa khỏi `raw`:** `pre_hook` của `fact_taxi_trips` xóa các `sourcefilename` không còn trong `raw.yellow_tripdata`, mất khoảng 0,5 giây. Trường hợp hiếm còn lại là nạp lại một file mà mọi dòng đều không hợp lệ: test `assert_fact_matches_staging` sẽ FAIL và chặn pipeline. Sửa bằng `.\tasks.ps1 dbt-build "fact_taxi_trips+ --full-refresh"` hoặc `dbt build --full-refresh -s fact_taxi_trips+`.

## Bảo mật

- Giao diện Mage chỉ mở trên máy này (`127.0.0.1:6789` trong `docker-compose.yml`). Giao diện có terminal và chạy được code trên thư mục repo, nên không mở ra mạng LAN.
- **Đổi mật khẩu tài khoản owner của Mage** (góc phải giao diện > Settings > Users) nếu vẫn dùng mặc định.
- Không commit `ALERT_WEBHOOK_URL`: đặt trong `.env`, file này đã nằm trong `.gitignore`.

Xem hoặc tạm dừng trigger: giao diện Mage > `nyc_taxi_e2e` > **Triggers** (hoặc sửa `status: inactive` trong `triggers.yaml` rồi khởi động lại container).

**Điều kiện để lịch chạy được:**
- Docker Desktop và container `nyc-mage` phải đang chạy vào giờ đã hẹn. Container có `restart: unless-stopped`, nên tự lên lại khi Docker Desktop khởi động. Bật *Start Docker Desktop when you sign in* trong Docker Desktop để không phải mở tay.
- Máy tắt hoặc ngủ đúng giờ hẹn thì lượt đó **không được chạy bù**; chạy tay bằng `.\tasks.ps1 e2e`.
- Không mở file DuckDB để ghi (DBeaver, `dbt` chạy tay) vào giờ hẹn. Power BI không ảnh hưởng vì đọc Parquet.

**Phạm vi dữ liệu:** ingestion, staging và Fact giới hạn chuyến đi 2024–2025. Khi tất cả 24 tháng đã nạp, mỗi lượt theo lịch bỏ qua bước nạp, build lại staging/Dimension/mart, chạy test, QA và xuất lại Parquet. Muốn nạp tháng mới (2026 trở đi) phải mở rộng phạm vi ở `load_trips_to_raw.py` (danh sách tháng), cờ `is_pickup_out_of_period` của staging và `dim_date`.

## Khi một bước lỗi

| Bước | Xem ở đâu | Thường gặp |
|---|---|---|
| Nạp chuyến đi | Log block; `select * from control.etl_control order by batch_id desc` | TLC chưa có file (HTTP 403/404), mất mạng: chạy lại sau. `Schema drift: file thiếu cột bắt buộc ...`: cập nhật `TARGET` trong `load_trips_to_raw.py` (map tên cột mới), rồi nạp lại file đó |
| dbt build | Log block; `dbt/logs/dbt.log`, `dbt/target/run_results.json` | Test dbt FAIL; file DuckDB bị khóa vì tiến trình khác đang mở |
| QA | `docs/test_plans_and_logs/runs/run_<thời điểm>.md` | Kiểm tra FAIL: xem cột "Thực tế" |
| Xuất Power BI | Log block | File DuckDB bị khóa |

Chạy lại sau khi sửa: `.\tasks.ps1 e2e`. Các bước đều chạy lại được an toàn: tháng đã nạp được bỏ qua, Fact không trùng, mart và Parquet được ghi đè.
