# Báo cáo QA phần Khoa — Staging → Dimension

## Thiết kế đã đọc từ code

Repository có SQL tạo/nạp tám Dimension trong schema `dds`:

| Dimension | Nguồn/quy tắc | Surrogate key |
|---|---|---|
| DimDate | Sinh ngày năm 2024–2025 | DateSK |
| DimTime | Sinh 24 × 60 phút | TimeSK |
| DimLocation | `stage.stg_taxi_zone_lookup` | LocationSK |
| DimVendor | Trips; mã ngoài 1/2 gắn nhãn Unknown | VendorSK |
| DimPaymentType | Trips; payment 0 gắn nhãn Unknown | PaymentTypeSK |
| DimRateCode | Trips; NULL chuyển thành ID 99/Unknown | RateCodeSK |
| DimPassengerGroup | Ba nhóm tĩnh | PassengerGroupSK |
| DimDistanceGroup | Ba nhóm tĩnh | DistanceGroupSK |

DDL chèn Unknown member `SK=-1` cho mỗi Dimension. Tên `DimDate`, `DateSK` không đặt trong dấu ngoặc kép nên PostgreSQL lưu tên vật lý chữ thường (`dimdate`, `datesk`).

## Kết quả kiểm thử

Trong Smoke run `20261026T034420Z`, PostgreSQL truy cập được nhưng không có bảng trong schema `dds`; truy vấn catalog `pg_tables` cũng trả về rỗng. Cả tám Dimension Smoke Test **FAIL** vì bảng chưa tồn tại, không phải lỗi kết nối. Tám Dimension Deep Tests, key mapping và label checks **BLOCKED** do Smoke chưa đạt.

## An toàn, hạn chế và việc tiếp theo

- Không chạy `warehouse/01_create_dimensions.sql`: file có `DROP TABLE IF EXISTS ... CASCADE`, có thể xóa bảng hiện có và đối tượng phụ thuộc.
- Không chạy `warehouse/02_load_dimensions.sql`: file append bằng `INSERT`; chạy lại có thể tạo dòng trùng.
- Kiểm thử uniqueness, natural-key mapping, expected row counts và nhãn chuẩn hóa sẽ chạy sau khi Dimensions được tạo/nạp trong môi trường được xác nhận.
- Idempotency và negative fixtures cần database tạm cách ly; hiện chưa có database test riêng.
- Fact chưa có trong repository, nên test Fact/tích hợp cuối pipeline vẫn `BLOCKED`.

Kết quả chi tiết: `docs/02_test_plans_and_logs/runs/run_20261026T034420Z.md`.
