# NYC TAXI - HƯỚNG DẪN TRIỂN KHAI TẦNG DIMENSION (DDS)

Tài liệu này hướng dẫn cách khởi tạo và nạp dữ liệu cho các bảng Dimension thuộc mô hình kho dữ liệu NYC Yellow Taxi.
- **Người phụ trách:** Khoa (Người 2)
- **Nguồn dữ liệu:** `stage.stg_yellow_taxi_trips`, `stage.stg_taxi_zone_lookup` (do Vân phụ trách nạp).
- **Đích đến:** Schema `dds` (PostgreSQL).

---

## 1. Thông tin bàn giao kiểm thử (Dành cho Tuấn)

Dưới đây là các thông tin cấu trúc để Tuấn xây dựng Test Plan và kịch bản đối chiếu dữ liệu.

### 1.1. Danh sách bảng và Surrogate Key (Khóa chính)
Toàn bộ 8 bảng Dimension được sử dụng khóa chính (Surrogate Key) tự tăng kiểu `SERIAL`.

| Tên bảng trong CSDL | Cột Surrogate Key (PK) | Nguồn cấp dữ liệu |
| :--- | :--- | :--- |
| `dds.DimDate` | `DateSK` | Tự động sinh (Generate Series 2024-2025) |
| `dds.DimTime` | `TimeSK` | Tự động sinh (Generate Series 24h) |
| `dds.DimLocation` | `LocationSK` | `stage.stg_taxi_zone_lookup` |
| `dds.DimVendor` | `VendorSK` | `stage.stg_yellow_taxi_trips` |
| `dds.DimPaymentType` | `PaymentTypeSK` | `stage.stg_yellow_taxi_trips` |
| `dds.DimRateCode` | `RateCodeSK` | `stage.stg_yellow_taxi_trips` |
| `dds.DimPassengerGroup` | `PassengerGroupSK` | Quy tắc tĩnh (Hardcode theo khoảng) |
| `dds.DimDistanceGroup`| `DistanceGroupSK` | Quy tắc tĩnh (Hardcode theo khoảng) |

*Lưu ý quan trọng:* Tất cả 8 bảng đều đã được chèn mặc định dòng có Surrogate Key = `-1` mang giá trị `Unknown` (Không xác định).

### 1.2. Script thực thi
*   `01_create_dimensions.sql`: DDL tạo schema `dds` và cấu trúc 8 bảng.
*   `02_load_dimensions.sql`: DML (ETL) lọc trùng (`DISTINCT`), biến đổi và nạp dữ liệu.

### 1.3. Kết quả chạy thử (Expected Results)
Để Tuấn có thể xác nhận Test Case là PASS:
*   Mã Vendor 6, 7 -> Ánh xạ thành `Unknown`.
*   Mã Payment 0 (Flex Fare) -> Ánh xạ thành `Unknown`.
*   Mã Ratecode NULL hoặc 99 -> Gán ID 99, ánh xạ thành `Unknown`.
*   Không có dòng trùng lặp hoàn toàn về ID tự nhiên trong các bảng Dimension (đã bọc `SELECT DISTINCT`).
*   Quá trình chạy lệnh không báo lỗi `ERROR`, kết quả in ra màn hình `INSERT 0 1` (đối với script 1) và `INSERT 0 ...` với script 2.

---

## 2. Hướng dẫn chạy Script (Dành cho người tiếp theo / Thịnh)

**Điều kiện tiên quyết:**
1. Đã pull nhánh chứa code này về máy.
2. Môi trường Docker đang chạy (đèn xanh ở Docker Desktop).
3. Đã chạy lệnh `docker compose up -d` và container `nyc-postgres` đang `healthy`.
4. Staging data đã được nạp (hoặc nạp ít nhất 1 tháng dữ liệu để làm mốc test).

### Bước 1: Khởi tạo bảng Dimension
Mở Terminal (PowerShell) tại thư mục gốc của project (NYC_TAXI), chạy lệnh sau để thiết lập cấu trúc:

```powershell
Get-Content warehouse\01_create_dimensions.sql | docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging
```
*Kết quả mong đợi:* Hệ thống báo `CREATE SCHEMA`, `CREATE TABLE` và chèn thành công dòng `-1`.

### Bước 2: Nạp dữ liệu vào Dimension
Tiếp tục chạy lệnh sau để load dữ liệu từ `stage` sang `dds`:

```powershell
Get-Content warehouse\02_load_dimensions.sql | docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging
```
*Kết quả mong đợi:* Hệ thống lọc trùng và chèn dữ liệu vào bảng, báo `INSERT 0 [số dòng]`. Quá trình mất khoảng 10-30 giây.

---

## 3. Lưu ý tra cứu khóa khi nạp Fact (Dành cho Thịnh)

Khi xây dựng bảng `FactTaxiTrip`, việc tra cứu khóa Dimension cần tuân thủ quy tắc sau để không làm mất dữ liệu doanh thu:

1. **Sử dụng LEFT JOIN:** Lấy bảng Stage làm gốc, `LEFT JOIN` với bảng Dimension thông qua mã tự nhiên gốc (ví dụ: `stage.vendor_id = dds.DimVendor.VendorID`).
2. **Xử lý mồ côi bằng COALESCE:** Với các dòng JOIN bị trượt (thường do file nguồn rác), giá trị Surrogate Key sẽ trả về NULL. Phải dùng hàm `COALESCE` bọc lại để ném nó về dòng `-1` đã tạo sẵn.
   *Ví dụ SQL mẫu:* `COALESCE(dim.VendorSK, -1) AS VendorSK`
3. **Cột Location:** Tên cột trong bảng Stage đã được Vân ép về snake_case (`location_id`). Khi join với `DimLocation`, nhớ dùng đúng tên này.