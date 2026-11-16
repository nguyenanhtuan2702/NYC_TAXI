# Kế hoạch kiểm thử ETL: Stage và Dimension

**Ngày khảo sát:** 26/10/2026  
**Phạm vi:** kiểm thử Source → Staging → Dimension theo repository hiện có.

## Môi trường đã xác minh

- Repository cấu hình PostgreSQL 17, Docker Compose và Mage; không có cấu hình SQL Server. Bộ test tuân theo PostgreSQL hiện hữu.
- Stage: `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup`; log ETL: `control.etl_control`.
- SQL tạo 8 Dimension: `DimDate`, `DimTime`, `DimLocation`, `DimVendor`, `DimPaymentType`, `DimRateCode`, `DimPassengerGroup`, `DimDistanceGroup` trong schema `dds`.
- Tên không đặt trong dấu ngoặc kép như `DimDate`/`DateSK` được PostgreSQL lưu chữ thường (`dimdate`/`datesk`). Runner dùng tên vật lý này.
- `warehouse/01_create_dimensions.sql` có `DROP TABLE ... CASCADE`; `warehouse/02_load_dimensions.sql` dùng `INSERT`. Runner không gọi hai script này.
- Không có Fact table, Fact ETL hoặc pipeline end-to-end trong repository.

## Lệnh điều khiển

```powershell
python tests\run_quality_tests.py --suite smoke
python tests\run_quality_tests.py --suite deep
python tests\run_quality_tests.py --suite all
```

`deep` và `all` luôn chạy Preflight rồi Smoke trước. Smoke thất bại sẽ chặn test phụ thuộc. Dùng `--scope stage` hoặc `--scope dimension` để chạy riêng một tầng. Full-table scans chỉ chạy khi thêm `--include-large-scans`.

Mọi lần chạy tạo JSON và Markdown trong `docs/02_test_plans_and_logs/runs/`. Kết nối được ép `read-only`; mỗi truy vấn qua `psql` nằm trong `BEGIN READ ONLY` rồi kết thúc bằng `ROLLBACK`. Không có ETL/DDL/DML nào được gọi.

## Test plan

| Test ID | Tầng | Kiểm tra | Kỳ vọng |
|---|---|---|---|
| PF-REPO-01 | Preflight | File loader, DDL và SQL profiling | File cần thiết tồn tại |
| PF-DIALECT-01 | Preflight | Database được cấu hình | PostgreSQL 17, không phải SQL Server |
| PF-ENV-01 | Preflight | Tên biến kết nối | Đủ biến; không in giá trị |
| PF-COMPOSE-01 | Preflight | Docker Compose parse | `docker compose config --quiet` thành công |
| PF-STACK-01 | Preflight | PostgreSQL service | Đang chạy |
| PF-MAGE-01 | Preflight | Mage service cho loader | Đang chạy nếu cần xác minh ETL operational |
| PF-DB-CONNECT / PF-DB-READONLY | Preflight | Kết nối và chế độ giao dịch | Kết nối được; `transaction_read_only=on` |
| STG-SM-01..04 | Stage Smoke | Bảng trips, lookup, control; file nguồn/loader | Đọc được; không tải/nạp dữ liệu |
| STG-ETL-01 | Stage Smoke | Thực thi loader | Chỉ chạy trên database tạm; hiện BLOCKED vì loader ghi/xóa dữ liệu |
| DIM-SM-* | Dimension Smoke | Từng Dimension thực tế | Bảng/cột đọc được; có SK `-1` |
| STG-SCH-01..02 | Stage Deep | Cột và kiểu dữ liệu 2 bảng Stage | Khớp DDL |
| STG-CMP-01 | Stage Deep | Audit fields bắt buộc | `source_file_name` và `load_datetime` NOT NULL ở cả 2 bảng |
| STG-REC-01 | Stage Deep | ETL control | Batch SUCCESS có `rows_read=rows_loaded`, `rows_rejected=0` |
| STG-VAL-01 | Stage Deep | NULL, thời gian ngược, khoảng cách/tiền bất thường | Ghi số liệu; chưa có ngưỡng nghiệp vụ để PASS/FAIL |
| STG-DUP-01 | Stage Deep | Trùng `(source_file_name, source_row_number)` | Không có nhóm trùng |
| STG-REC-02 | Stage Deep | Số dòng theo file so với log SUCCESS mới nhất | Khớp `rows_loaded` |
| DIM-SCH-* | Dimension Deep | SK/natural key, NULL, uniqueness, Unknown | Khóa không NULL/trùng; một dòng `SK=-1` |
| DIM-COUNT-* | Dimension Deep | Kích thước ngày/giờ/nhóm tĩnh | Date 732, Time 1.441, Passenger/Distance 4 dòng mỗi bảng, gồm Unknown |
| DIM-MAP-* | Dimension Deep | Stage key → Dimension và label | Khóa ánh xạ và nhãn khớp SQL |
| DIM-IDEMP-01 | Dimension Deep | Chạy lại ETL | Chỉ chạy trên DB tạm; hiện BLOCKED |
| NEG-FIXTURE-01 | Negative | Fixture sai được assertion phát hiện | Chỉ chạy trên PostgreSQL tạm; hiện NOT RUN |
| FACT-INT-01 | Integration | Fact, foreign key và measures | BLOCKED đến khi có Fact implementation |

Stage profile và mapping có thể quét bảng trips lớn nên mặc định `NOT RUN`; thêm `--include-large-scans` để chạy. Các anomaly không tự động bị coi là lỗi vì Stage giữ dữ liệu nguồn thô và repo chưa định nghĩa ngưỡng chấp nhận.

## Quy tắc trạng thái

- `PASS`: truy vấn thật chạy và assertion đạt.
- `FAIL`: truy vấn thật chạy nhưng phát hiện thiếu thành phần hoặc vi phạm assertion.
- `BLOCKED`: thiếu kết nối, bảng/phụ thuộc hoặc database test riêng.
- `NOT RUN`: bài test được hoãn hoặc không được chọn.
- `NOT APPLICABLE`: có số liệu nhưng chưa có quy tắc nghiệp vụ để kết luận đạt/trượt.

## Giới hạn tự động hóa và phương án thay thế

- Không kiểm thử idempotency trên DB hiện tại: script tạo Dimension có `DROP TABLE ... CASCADE`, còn script load chỉ `INSERT`, nên có thể xóa hoặc nhân đôi dữ liệu.
- Không chèn fixture âm vào database dùng chung. Cần PostgreSQL database tạm cách ly; sau khi có thì chạy negative/idempotency suite ở môi trường đó.
- Khi chưa có Fact, giữ `FACT-INT-01` ở `BLOCKED`; cần script tạo/load Fact, grain, khóa và quy tắc measures trước khi mở test.
