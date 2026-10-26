# Báo cáo QA phần Vân — Source → Staging

## Mục tiêu và triển khai

Stage giữ dữ liệu Yellow Taxi và Taxi Zone Lookup để các tầng sau đọc; code hiện giữ nguyên bất thường từ nguồn. Mage đọc Parquet bằng PyArrow, nạp theo batch 200.000 dòng qua PostgreSQL `COPY`, bổ sung `source_file_name`, `source_row_number`, `batch_id`, và ghi lịch sử vào `control.etl_control`.

Pipeline trips giới hạn dữ liệu 2024–2025, tự tải file còn thiếu, thử lại tải/kết nối, xử lý từng file trong transaction và ghi trạng thái `SUCCESS`/`FAILED`. Khi file đã có log, pipeline xóa dòng Stage của đúng file trước khi nạp lại; vì vậy QA không thực thi loader trên database hiện tại.

## Kết quả Smoke và Deep Tests

Run `20261026T034420Z` kết nối `nyc_taxi_staging` trong transaction read-only. Bảng trips, Zone Lookup và ETL control đều đọc được. Zone Lookup có chính xác 265 dòng; control có 3 dòng. Planner ước lượng khoảng 9.555.824 trip rows, còn full scan đếm chính xác 9.554.778 dòng. Raw local có một Parquet lúc chạy; test không tải hoặc nạp file.

Deep run tổng hợp `20261026T034420Z`:

| Kiểm tra | Kết quả |
|---|---|
| Schema trips (24 cột) và Zone Lookup (7 cột) | PASS — khớp tên cột và kiểu dữ liệu DDL |
| Audit fields bắt buộc | PASS — 4 cột `source_file_name`/`load_datetime` là NOT NULL |
| ETL control | PASS — 3 log SUCCESS; không log SUCCESS nào lệch `rows_read`/`rows_loaded` hoặc `rows_rejected` |
| Profiling | NOT APPLICABLE — 9.554.778 dòng; pickup/dropoff NULL 0; dropoff trước pickup 180; distance ≤ 0: 215.764; fare âm: 136.567; total âm: 115.895. Repo chưa đặt ngưỡng cho anomaly |
| Trùng `(source_file_name, source_row_number)` | PASS — 0 khóa trùng |
| Đối soát file Stage/log | PASS — 0 file lệch so với log SUCCESS mới nhất |

Toàn lượt `all` có 19 PASS, 8 FAIL, 14 BLOCKED, 1 NOT RUN và 1 NOT APPLICABLE. Cả 8 FAIL là Dimension thiếu trong database; Stage read checks và các assertion đã chạy đều PASS, anomaly profile là NOT APPLICABLE. Stage ETL và Mage runtime bị BLOCKED: Mage không chạy, loader có thao tác DELETE/COPY, và chưa có database thử nghiệm riêng. Negative fixture chưa chạy vì cùng lý do thiếu database cách ly. Không có ETL, DDL hoặc DML chạy trong QA.

## Hạn chế và việc tiếp theo

- Full scans gây tải CPU/IO đáng kể; vì vậy runner mặc định tắt chúng và chỉ chạy khi thêm `--include-large-scans`.
- Các anomaly chưa có ngưỡng nghiệp vụ; số liệu cần được diễn giải theo quy tắc đã thống nhất, không tự coi mọi giá trị âm/NULL là lỗi.
- Kết quả hiện xác nhận khả năng đọc, schema và control logs; chưa khẳng định toàn bộ dữ liệu source đúng.
- Chưa có Fact nên không có kiểm thử end-to-end tới Fact.

Kết quả chi tiết: `docs/02_test_plans_and_logs/runs/run_20261026T034420Z.md`.
