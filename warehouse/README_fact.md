# NYC TAXI - HƯỚNG DẪN TRIỂN KHAI & BÀN GIAO TẦNG FACT (DDS)

Tài liệu này mô tả chi tiết thiết kế, quy tắc làm sạch dữ liệu, quy trình ETL và kịch bản kiểm thử nghiệm thu cho bảng dữ kiện trung tâm **`dds.FactTaxiTrip`** thuộc mô hình kho dữ liệu NYC Yellow Taxi (Star Schema).

- **Người phụ trách:** Thịnh (Người 3 - Tầng Fact)
- **Nguồn dữ liệu:** `stage.stg_yellow_taxi_trips` (do Vân nạp) kết hợp 8 bảng Dimension trong `dds` (do Khoa tạo).
- **Căn cứ thiết kế:** Tuân thủ 100% tài liệu `modeling.pdf` (Trang 3–6) và phân công `Giai đoạn 1 NYC Yellow Taxi Trip.pdf`.
- **Đích đến:** `dds.FactTaxiTrip` (PostgreSQL) và model dbt `dbt/models/dds/facts/fact_taxi_trips.sql`.
- **Đối tượng bàn giao:** Bee (Người 4 - QA/Tester), Tuấn (Tổng hợp báo cáo), và người làm Power BI / OLAP tiếp theo.

---

## 1. Đặc tả Bảng dữ kiện (Fact Table Specification)

### 1.1. Grain (Độ mịn / Hạt của dữ kiện)
Mỗi dòng trong bảng `dds.FactTaxiTrip` biểu diễn **một chuyến đi taxi đơn lẻ đã hoàn thành** được ghi nhận trên hệ thống đồng hồ tính cước của xe Yellow Taxi.

### 1.2. Danh sách Khóa ngoại (11 Foreign Keys tới 8 Dimension)
Toàn bộ khóa ngoại tham chiếu đến khóa Surrogate Key (`SERIAL`) của 8 bảng Dimension. Cơ chế ETL sử dụng `LEFT JOIN` và bọc hàm `COALESCE(dim.SK, -1)` để bảo toàn 100% doanh thu, đưa các bản ghi mồ côi hoặc thiếu thông tin về dòng mặc định `-1 (Unknown)`.

| Tên cột Foreign Key | Kiểu | Bảng Dimension tham chiếu | Khóa tự nhiên nguồn | Ghi chú nghiệp vụ |
| :--- | :--- | :--- | :--- | :--- |
| `PickupDateSK` | INT | `dds.DimDate(DateSK)` | `tpep_pickup_datetime::date` | Ngày đón khách |
| `DropoffDateSK` | INT | `dds.DimDate(DateSK)` | `tpep_dropoff_datetime::date` | Ngày trả khách |
| `PickupTimeSK` | INT | `dds.DimTime(TimeSK)` | `pickup (hour, minute)` | Khung giờ đón khách |
| `DropoffTimeSK` | INT | `dds.DimTime(TimeSK)` | `dropoff (hour, minute)` | Khung giờ trả khách |
| `PickupLocationSK` | INT | `dds.DimLocation(LocationSK)` | `pu_location_id` | Điểm đón (Taxi Zone) |
| `DropoffLocationSK`| INT | `dds.DimLocation(LocationSK)` | `do_location_id` | Điểm trả (Taxi Zone) |
| `VendorSK` | INT | `dds.DimVendor(VendorSK)` | `vendor_id` | Hãng xe (CMT / VTS) |
| `PaymentTypeSK` | INT | `dds.DimPaymentType(PaymentTypeSK)` | `payment_type` | Thẻ tín dụng, tiền mặt,... |
| `RateCodeSK` | INT | `dds.DimRateCode(RateCodeSK)` | `COALESCE(ratecode_id, 99)` | Tiêu chuẩn, JFK, Newark,... |
| `PassengerGroupSK`| INT | `dds.DimPassengerGroup(PassengerGroupSK)` | `passenger_count` | 1 người, 2-4 người, 5+ |
| `DistanceGroupSK` | INT | `dds.DimDistanceGroup(DistanceGroupSK)` | `trip_distance` | <2mi, 2-5mi, >5mi |

### 1.3. Base Measures vật lý (Lưu trực tiếp trong Fact - Additive Measures)
Theo đúng trang 3 của tài liệu `modeling.pdf`, Fact lưu 14 measures cơ sở có thể cộng dồn theo mọi chiều phân tích:

| Tên cột Measure | Kiểu | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- |
| `TotalTrips` | INT | Luôn bằng `1` cho mỗi bản ghi hợp lệ. Dùng `SUM(TotalTrips)` để đếm tổng số chuyến. |
| `PassengerCount` | INT | Số lượng hành khách ghi nhận trên xe. |
| `TripDistance` | DOUBLE | Quãng đường di chuyển (dặm - miles). |
| `TripDurationMinutes` | DOUBLE | Thời lượng chuyến đi tính bằng phút: `(DropoffDateTime - PickupDateTime)`. |
| `FareAmount` | DOUBLE | Tiền cước chính tính theo đồng hồ. |
| `Extra` | DOUBLE | Phụ phí giờ cao điểm ($1.00) / ban đêm ($0.50). |
| `MTATax` | DOUBLE | Thuế/phí MTA ($0.50). |
| `TipAmount` | DOUBLE | Tiền boa ghi nhận (chủ yếu từ thanh toán thẻ tín dụng). |
| `TollsAmount` | DOUBLE | Tiền phí cầu đường, hầm qua trạm thu phí. |
| `ImprovementSurcharge` | DOUBLE | Phí cải thiện hạ tầng và dịch vụ taxi. |
| `CongestionSurcharge` | DOUBLE | Phụ phí chống ùn tắc giao thông Manhattan ($2.50). |
| `AirportFee` | DOUBLE | Phụ phí đưa/đón tại các sân bay JFK, LaGuardia ($1.25). |
| `CBDCongestionFee` | DOUBLE | Phí ùn tắc khu vực trung tâm Manhattan (áp dụng từ 2025). |
| `TotalAmount` | DOUBLE | Tổng số tiền thanh toán thực tế của hành khách. |

### 1.4. Audit & Lineage Metadata (Kiểm toán & Nguồn gốc dữ liệu)
Bảng Fact được trang bị 4 cột metadata kỹ thuật chuẩn Kimball để phục vụ **nạp gia tăng (Incremental Load)**, theo dõi nguồn gốc dữ liệu (Data Lineage) và kiểm toán hệ thống:

| Tên cột Metadata | Kiểu | Ý nghĩa kỹ thuật |
| :--- | :--- | :--- |
| `SourceFileName` | VARCHAR(200) | Tên file Parquet nguồn gốc (ví dụ: `yellow_tripdata_2025-01.parquet`). |
| `SourceRowNumber` | BIGINT | Thứ tự dòng trong file Parquet gốc (Lineage tracking). |
| `BatchID` | BIGINT | Mã phiên nạp (Batch ID) từ pipeline Mage / Staging. |
| `LoadedAt` | TIMESTAMP | Thời điểm bản ghi được nạp vào Fact (Watermark). |

### 1.5. Semantic Measures (Được tính toán động trên BI / OLAP - Không lưu vật lý)
Theo trang 4 của `modeling.pdf`, các measures phái sinh sau được định nghĩa bằng công thức động (DAX / SQL aggregations) để tối ưu dung lượng và tránh sai sót khi tổng hợp nhiều chiều:
- **`AvgRevenuePerTrip`** = `SUM(TotalAmount) / SUM(TotalTrips)`
- **`AvgPassengersPerTrip`** = `SUM(PassengerCount) / SUM(TotalTrips)`
- **`AvgDistancePerTrip`** = `SUM(TripDistance) / SUM(TotalTrips)`
- **`AvgTripDuration`** = `SUM(TripDurationMinutes) / SUM(TotalTrips)`
- **`AvgSpeed`** = `SUM(TripDistance) / (SUM(TripDurationMinutes) / 60.0)` *(mph)*
- **`AvgTipRate`** = `SUM(TipAmount) / NULLIF(SUM(FareAmount), 0) * 100%`

---

## 2. Quy tắc Làm sạch Dữ liệu (ETL Data Quality Rules)

Trong quá trình nạp từ `stage.stg_yellow_taxi_trips` sang `dds.FactTaxiTrip`, các bản ghi vi phạm các điều kiện sau sẽ bị loại bỏ:
1. **Lỗi thời gian di chuyển:** `tpep_dropoff_datetime <= tpep_pickup_datetime` (thời lượng chuyến đi $\le 0$).
2. **Ngoài phạm vi nghiên cứu:** Chuyến đi có giờ đón trước `2024-01-01` hoặc từ `2026-01-01` trở đi.
3. **Lỗi tài chính âm:** `fare_amount < 0` hoặc `total_amount < 0` (các giao dịch tranh chấp, hủy cước, hoàn tiền).
4. **Lỗi cự ly âm:** `trip_distance < 0`.

---

## 3. Quy trình Nạp Gia tăng & Hướng dẫn Thực thi (Incremental Load)

Quy trình nạp Fact được nâng cấp toàn diện theo kiến trúc **Incremental Load (Nạp gia tăng)** bảo toàn giao dịch (`BEGIN ... COMMIT`), hoàn toàn không sử dụng lệnh `TRUNCATE` hay `DROP` phá hủy bảng:
1. **Lần chạy đầu tiên (Initial Load):** Bảng Fact chưa có dữ liệu, toàn bộ dữ liệu hợp lệ từ Staging sẽ được nạp vào Fact.
2. **Các lần chạy tiếp theo (Incremental Run):** Pipeline tự động so sánh Watermark (`BatchID` lớn hơn `MAX(BatchID)` đã có trong Fact hoặc các file mới chưa từng nạp). Do đó:
   - Nếu không có dữ liệu mới: Trả về `INSERT 0 0` an toàn, không nhân đôi số dòng, không làm gián đoạn các truy vấn đang đọc.
   - Khi có file mới: Chỉ nạp riêng file mới đó, thời gian nạp chỉ vài chục giây thay vì chạy lại toàn bộ lịch sử nhiều năm.
   - Nếu gặp sự cố giữa chừng: Khối giao dịch (`BEGIN; ... COMMIT;`) tự động `ROLLBACK`, bảng Fact cũ không bao giờ bị mất dữ liệu.

### Bước 1: Khởi tạo bảng Fact & Indexes (Idempotent DDL)
Chạy lệnh trong PowerShell tại thư mục gốc dự án:
```powershell
Get-Content warehouse\03_create_fact.sql | docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging
```

### Bước 2: Nạp gia tăng vào Fact từ Staging (Incremental Load)
```powershell
Get-Content warehouse\04_load_fact.sql | docker compose exec -T postgres psql -U taxi_user -d nyc_taxi_staging
```

### Bước 3: Kiểm thử đối chiếu dữ liệu & phân phối Batch
```powershell
Get-Content warehouse\05_verify_fact.sql | docker compose exec -T postgres psql -P pager=off -U taxi_user -d nyc_taxi_staging
```

---

## 4. Tích hợp dbt (Data Build Tool)

Dự án đã được cấu hình sẵn sàng cho dbt trong thư mục `dbt/`:
- **File cấu hình:** `dbt/dbt_project.yml` và `dbt/profiles.yml`.
- **Macro xử lý schema:** `dbt/macros/generate_schema_name.sql` (giữ đúng schema `dds`).
- **Model Fact:** `dbt/models/dds/facts/fact_taxi_trips.sql`.
- **Tests tự động:** `dbt/models/dds/facts/schema.yml` (kiểm tra `not_null` và `relationships` toàn vẹn khóa ngoại).

Chạy kiểm thử dbt:
```powershell
docker compose exec -T mage dbt test --project-dir /home/src/dbt --profiles-dir /home/src/dbt
```
*Kết quả:* `Done. PASS=16 WARN=0 ERROR=0 SKIP=0 TOTAL=16`

---

## 5. Thông tin Bàn giao Kiểm thử (Dành cho Bee & Tuấn)

Dưới đây là các tiêu chuẩn nghiệm thu và kết quả đo đạc thực tế để Bee đưa vào **Test Plan** và Tuấn đưa vào **Báo cáo**:

### 5.1. Tiêu chí Nghiệm thu (Acceptance Criteria)
- [x] **Toàn vẹn khóa ngoại (Referential Integrity):** Không có bản ghi nào bị lỗi trỏ sai khóa Dimension (`0 lỗi`). Toàn bộ 16 tests của dbt đạt **PASS 100%**.
- [x] **Bảo toàn dữ liệu:** Tỷ lệ nạp thành công đạt trên 95%. Tất cả các dòng bị loại (khoảng 4-5%) đều có lý do chính đáng được phân loại rõ ràng (cước âm, thời gian âm).
- [x] **Cơ chế Idempotent:** Khi chạy lại script `04_load_fact.sql`, dữ liệu cũ được dọn dẹp và nạp lại chính xác, không bị nhân đôi số dòng.

### 5.2. Kết quả Đo đạc Thực tế trên 2 Mốc Dữ liệu

| Chỉ số kiểm thử | Mốc 1: Tháng 01/2025 (1 file) | Mốc 2: Tháng 01 & 02/2025 (2 file) |
| :--- | :--- | :--- |
| **Tổng dòng Staging đọc vào** | 3.475.226 dòng | **7.052.769 dòng** |
| **Tổng dòng Fact nạp thành công** | 3.328.747 dòng (95,79%) | **6.718.093 dòng (95,25%)** |
| **Tổng dòng bị loại (Dữ liệu rác)** | 146.479 dòng (4,21%) | **334.676 dòng (4,75%)** |
| - *Lý do tiền cước âm (`fare < 0`)* | 144.118 dòng | 329.839 dòng |
| - *Lý do tổng tiền âm (`total < 0`)* | 63.037 dòng | 144.476 dòng |
| - *Lý do thời gian vô lý (`dropoff <= pickup`)* | 2.051 dòng | 4.398 dòng |
| **Tỷ lệ khóa mồ côi (Unknown = -1)** | Ngày/Giờ/Vị trí/Hãng xe: `0` dòng | Ngày/Giờ/Vị trí/Hãng xe: `0` dòng |
| **Thời lượng chuyến đi trung bình** | 15.06 phút | **15.25 phút** |
| **Quãng đường di chuyển trung bình** | 5.39 miles (~8.6 km) | **5.54 miles** |
| **Tiền cước trung bình (`FareAmount`)** | $18.33 | **$18.25** |
| **Tổng tiền trung bình (`TotalAmount`)** | $27.12 | **$26.90** |

---

## 6. Hướng dẫn Phân tích & Viết DAX (Dành cho Người làm Power BI / OLAP)

Khi kết nối Power BI hoặc viết các truy vấn OLAP Data Marts, bảng `FactTaxiTrip` liên kết với các bảng Dimension theo mô hình hình sao (Star Schema 1-n) như sau:

1. **Thống kê theo thời gian (Câu 1, Câu 4):**
   - Nối `FactTaxiTrip.PickupDateSK` ➔ `DimDate.DateSK`.
   - Nối `FactTaxiTrip.PickupTimeSK` ➔ `DimTime.TimeSK`.
2. **Thống kê doanh thu theo Quận / Hãng xe (Câu 2):**
   - Nối `FactTaxiTrip.PickupLocationSK` ➔ `DimLocation.LocationSK` (Lấy `DimLocation.Borough`).
   - Nối `FactTaxiTrip.VendorSK` ➔ `DimVendor.VendorSK` (Lấy `DimVendor.VendorName`).
3. **Thống kê hình thức thanh toán (Câu 3):**
   - Nối `FactTaxiTrip.PaymentTypeSK` ➔ `DimPaymentType.PaymentTypeSK`.
4. **Phân tích nhóm khách & cự ly (Câu 5):**
   - Nối `FactTaxiTrip.PassengerGroupSK` ➔ `DimPassengerGroup.PassengerGroupSK`.
   - Nối `FactTaxiTrip.DistanceGroupSK` ➔ `DimDistanceGroup.DistanceGroupSK`.
5. **Công thức DAX mẫu cơ bản:**
   ```dax
   Total Trips = SUM(FactTaxiTrip[TotalTrips])
   Total Revenue = SUM(FactTaxiTrip[TotalAmount])
   Avg Speed MPH = DIVIDE(SUM(FactTaxiTrip[TripDistance]), DIVIDE(SUM(FactTaxiTrip[TripDurationMinutes]), 60))
   Avg Tip Rate = DIVIDE(SUM(FactTaxiTrip[TipAmount]), SUM(FactTaxiTrip[FareAmount]))
   ```
