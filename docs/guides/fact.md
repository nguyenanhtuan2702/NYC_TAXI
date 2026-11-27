# Fact (DDS)

Tài liệu này mô tả chi tiết thiết kế, quy tắc làm sạch dữ liệu, quy trình ETL và kịch bản kiểm thử nghiệm thu cho bảng dữ kiện trung tâm **`dds.facttaxitrip`** của Star Schema, build bằng dbt-duckdb trên cùng file DuckDB với Mage (`data/warehouse/nyc_taxi.duckdb`).

- **Nguồn dữ liệu:** view `stage.stg_yellow_taxi_trips` kết hợp 8 bảng Dimension trong `dds` (xem [dimension.md](dimension.md)).
- **Căn cứ thiết kế:** tài liệu `docs/data_modeling/modeling.pdf` (trang 3–6).
- **Đích đến:** model dbt `dbt/models/dds/facts/fact_taxi_trips.sql` → `dds.facttaxitrip`.

---

## 0. Chạy và cơ chế nạp

| Mục | Giá trị |
| :--- | :--- |
| Model | `dbt/models/dds/facts/fact_taxi_trips.sql` → bảng `dds.facttaxitrip` |
| Nguồn | `ref('stg_yellow_taxi_trips')` (view staging) + 8 Dimension qua `ref()` |
| Điều kiện giữ dòng | `stg.is_valid_for_fact` (định nghĩa một chỗ trong staging, xem [staging.md](staging.md)) |
| Materialization | `incremental`, `incremental_strategy='delete+insert'`, `unique_key='sourcefilename'` |
| Lọc incremental | `stg.batch_id > max(batchid)` đã có trong Fact |

**Cơ chế nạp:**
- Lần đầu (hoặc `--full-refresh`): tạo bảng từ toàn bộ staging hợp lệ.
- Lần sau: chỉ lấy dòng có `batch_id` mới hơn batch lớn nhất trong Fact. Với các file trong lô mới, dbt **xóa mọi dòng Fact của file đó** rồi chèn lại. Nhờ vậy:
  - không có dữ liệu mới → không thay đổi gì (chạy 0,3 s);
  - nạp thêm file mới → chỉ chèn file đó;
  - **nạp lại một file đã có** (Mage thay dòng raw của file bằng batch mới) → dòng Fact cũ của file bị thay, **không trùng**.
- File bị xóa hẳn khỏi `raw`: `pre_hook` của model xóa các dòng Fact có `sourcefilename` không còn trong `raw.yellow_tripdata` trước mỗi lần chạy incremental.
- Nhóm cự ly tra theo khoảng nửa mở `[mindistance, mindistance của nhóm kế tiếp)`; mốc trên của nhóm cuối là `1e12` (không dùng `OR ... IS NULL`, vì điều kiện đó làm DuckDB không đẩy được bộ lọc `batch_id` xuống trước join, bước Fact chậm từ ~1 s lên ~50 s).

```powershell
.\tasks.ps1 dbt-build dds                       # build 8 Dimension + Fact + test
.\tasks.ps1 dbt-build fact_taxi_trips           # chỉ Fact (incremental) + test
docker compose exec -T -w /home/src/dbt mage dbt build --select fact_taxi_trips --full-refresh --profiles-dir .
```

**Test** (`dbt/models/dds/facts/schema.yml`, `dbt/tests/facts/`): `not_null` và `relationships` cho các khóa SK; `assert_fact_matches_staging` so số dòng Fact theo từng file với số dòng staging có `is_valid_for_fact` (bắt nạp trùng, mất dòng do join, file thiếu hoặc thừa).

**Kết quả 18/11/2026 trên 24 tháng (2024-01 → 2025-12):**

| Chỉ số | Giá trị |
| :--- | ---: |
| Dòng staging | 89.892.322 |
| Dòng Fact (`is_valid_for_fact`) | **85.745.246 (95,39%)** |
| Build đầy đủ | 94–137 s (bộ nhớ container < 1 GB sau build); 116 s sau khi thêm SCD2 cho Location |
| Incremental, không có dữ liệu mới | 0,3 s |
| Incremental sau khi nạp lại file 2024-01 | 7 s, tổng dòng không đổi, file 2024-01 mang batch mới |
| Test Fact | 18/18 PASS |

Khóa Unknown (`-1`) trong Fact: **0 dòng ở mọi khóa**. Hai trường hợp đặc biệt được xử lý trong Dimension:
- 759 chuyến đón cuối 2025 nhưng trả khách trong 01/2026 (muộn nhất 05/01/2026): `DimDate` kéo dài tới 2026-01-31 nên `DropoffDateSK` vẫn có ngày.
- 14.181.248 chuyến có `passenger_count` NULL (13,53 triệu, chủ yếu Flex Fare) hoặc 0 (0,66 triệu): gán nhóm `NONE` (`PassengerGroupSK = 0`), Fact join bằng `coalesce(passenger_count, 0)`.

Lưu ý Power BI: `DimDate` có tháng 01/2026 nhưng không có chuyến nào **đón** trong tháng đó; lọc theo `PickupDateSK` sẽ không thấy dữ liệu 2026.

---

## 1. Đặc tả Bảng dữ kiện (Fact Table Specification)

### 1.1. Grain (Độ mịn / Hạt của dữ kiện)
Mỗi dòng trong bảng `dds.facttaxitrip` biểu diễn **một chuyến đi taxi đơn lẻ đã hoàn thành** được ghi nhận trên hệ thống đồng hồ tính cước của xe Yellow Taxi.

### 1.2. Danh sách Khóa ngoại (11 Foreign Keys tới 8 Dimension)
Toàn bộ khóa ngoại tham chiếu đến Surrogate Key của 8 bảng Dimension (trong dbt: SK ổn định sinh từ khóa tự nhiên). Cơ chế ETL sử dụng `LEFT JOIN` và bọc hàm `COALESCE(dim.SK, -1)` để bảo toàn 100% doanh thu, đưa các bản ghi mồ côi hoặc thiếu thông tin về dòng mặc định `-1 (Unknown)`.

| Tên cột Foreign Key | Kiểu | Bảng Dimension tham chiếu | Khóa tự nhiên nguồn | Ghi chú nghiệp vụ |
| :--- | :--- | :--- | :--- | :--- |
| `PickupDateSK` | INT | `dds.DimDate(DateSK)` | `tpep_pickup_datetime::date` | Ngày đón khách |
| `DropoffDateSK` | INT | `dds.DimDate(DateSK)` | `tpep_dropoff_datetime::date` | Ngày trả khách |
| `PickupTimeSK` | INT | `dds.DimTime(TimeSK)` | `pickup (hour, minute)` | Khung giờ đón khách |
| `DropoffTimeSK` | INT | `dds.DimTime(TimeSK)` | `dropoff (hour, minute)` | Khung giờ trả khách |
| `PickupLocationSK` | INT | `dds.DimLocation(LocationSK)` | `pu_location_id` + giờ đón trong `[ValidFrom, ValidTo)` (SCD2) | Điểm đón (Taxi Zone) |
| `DropoffLocationSK`| INT | `dds.DimLocation(LocationSK)` | `do_location_id` + giờ trả trong `[ValidFrom, ValidTo)` (SCD2) | Điểm trả (Taxi Zone) |
| `VendorSK` | INT | `dds.DimVendor(VendorSK)` | `vendor_id` | Hãng xe (CMT / VTS) |
| `PaymentTypeSK` | INT | `dds.DimPaymentType(PaymentTypeSK)` | `payment_type` | Thẻ tín dụng, tiền mặt,... |
| `RateCodeSK` | INT | `dds.DimRateCode(RateCodeSK)` | `COALESCE(ratecode_id, 99)` | Tiêu chuẩn, JFK, Newark,... |
| `PassengerGroupSK`| INT | `dds.DimPassengerGroup(PassengerGroupSK)` | `coalesce(passenger_count, 0)` | Không ghi nhận (0/NULL), 1 người, 2-4 người, 5+ |
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

Trong quá trình nạp từ `stage.stg_yellow_taxi_trips` sang Fact, các bản ghi vi phạm các điều kiện sau sẽ bị loại bỏ. Từ 18/11/2026 các điều kiện này được tính một lần trong staging thành cờ `is_valid_for_fact`; Fact chỉ lọc `WHERE stg.is_valid_for_fact`:
1. **Lỗi thời gian di chuyển:** `tpep_dropoff_datetime <= tpep_pickup_datetime` (thời lượng chuyến đi $\le 0$).
2. **Ngoài phạm vi nghiên cứu:** Chuyến đi có giờ đón trước `2024-01-01` hoặc từ `2026-01-01` trở đi.
3. **Lỗi tài chính âm:** `fare_amount < 0` hoặc `total_amount < 0` (các giao dịch tranh chấp, hủy cước, hoàn tiền).
4. **Lỗi cự ly âm:** `trip_distance < 0`.

---

## 3. Cấu trúc dbt

Cách chạy xem [mục 0](#0-chạy-và-cơ-chế-nạp). Các file liên quan trong `dbt/`:
- **File cấu hình:** `dbt/dbt_project.yml` và `dbt/profiles.yml`.
- **Macro xử lý schema:** `dbt/macros/generate_schema_name.sql` (giữ đúng schema `dds`).
- **Model Fact:** `dbt/models/dds/facts/fact_taxi_trips.sql`.
- **Tests tự động:** `dbt/models/dds/facts/schema.yml` (`not_null`, `relationships`) và `dbt/tests/facts/assert_fact_matches_staging.sql`.

Chạy kiểm thử dbt:
```powershell
.\tasks.ps1 dbt-test fact_taxi_trips
```
*Kết quả 18/11/2026 (24 tháng):* `Done. PASS=18 WARN=0 ERROR=0`

---

## 4. Dùng Fact cho báo cáo

Power BI không đọc Fact trực tiếp. Dashboard đọc 5 OLAP mart tổng hợp từ Fact (xem [olap.md](olap.md)) và các Dimension, xuất ra Parquet bằng `.\tasks.ps1 export-bi` (xem [powerbi.md](powerbi.md)). Các measure phái sinh ở mục 1.5 được viết bằng DAX trong `powerbi/dax/measures.dax`, tính từ tổng của mart.
