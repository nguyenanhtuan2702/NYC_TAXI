# Staging: `raw` → `stage` (dbt trên DuckDB)

Tầng staging nằm giữa dữ liệu thô do Mage nạp (schema `raw`, xem [ingestion.md](ingestion.md)) và kho dữ liệu DDS (Dimension/Fact). Nhiệm vụ: đặt tên và kiểu dữ liệu thống nhất, tính các cột dẫn xuất, **gắn cờ** dữ liệu lỗi. Staging **không lọc dòng**: việc giữ hay bỏ một chuyến đi do tầng DDS quyết định, dựa trên các cờ ở đây.

## Các model

| Model dbt | Đối tượng trong DuckDB | Nguồn | Kiểu |
|---|---|---|---|
| `stg_taxi_zone_lookup` | `stage.stg_taxi_zone_lookup` | `raw.taxi_zone_lookup` | view |
| `stg_yellow_taxi_trips` | `stage.stg_yellow_taxi_trips` | `raw.yellow_tripdata` | view |

Dùng **view** vì DuckDB đọc dữ liệu theo cột rất nhanh: không tốn thêm dung lượng, luôn phản ánh `raw` mới nhất, và DDS chỉ đọc những cột cần. Đo trên 24 tháng (~90 triệu dòng): đếm toàn bộ cờ trên view ~15 s.

Các model Dimension/Fact đọc staging bằng `ref('stg_...')`. Model staging giữ đúng tên cột của bảng stage cũ (`vendor_id`, `pu_location_id`, ...), nên logic DDS không phải sửa.

### `stg_yellow_taxi_trips`

Giữ mọi cột của `raw.yellow_tripdata` (`store_and_fwd_flag` được `upper(trim())`), thêm:

| Cột | Ý nghĩa |
|---|---|
| `source_month` | Tháng của file nguồn, lấy từ tên file (`yellow_tripdata_2024-03.parquet` → `2024-03-01`) |
| `trip_duration_minutes` | `dropoff - pickup` tính bằng phút (âm nếu trả trước đón) |
| `component_total_amount` | Tổng các khoản thành phần (`fare + extra + mta_tax + tip + tolls + improvement + congestion + airport + cbd`, NULL coi là 0) |

**Cờ chất lượng** (kiểu BOOLEAN, luôn true/false):

| Cờ | Điều kiện | Số dòng (24 tháng) |
|---|---|---:|
| `is_vendor_unknown` | `vendor_id` NULL hoặc khác 1, 2 | 562.182 (0,63%) |
| `is_pickup_out_of_period` | giờ đón trước 2024-01-01 hoặc từ 2026-01-01 | 59 |
| `is_pickup_outside_source_month` | tháng của giờ đón khác tháng của file | 634 |
| `is_dropoff_before_pickup` | giờ trả sớm hơn giờ đón | 3.810 |
| `is_zero_duration` | giờ trả bằng giờ đón | 556.004 (0,62%) |
| `is_duration_over_24h` | chuyến dài hơn 24 giờ | 582 |
| `is_passenger_missing` | `passenger_count` NULL hoặc 0 | 16.364.542 (18,20%) |
| `is_distance_non_positive` | `trip_distance <= 0` | 2.179.263 (2,42%) |
| `is_speed_over_100mph` | vận tốc > 100 mph | 24.413 (0,03%) |
| `is_negative_amount` | `fare_amount` hoặc `total_amount` âm | 3.587.479 (3,99%) |
| `is_surcharge_missing` | `congestion_surcharge` NULL (Flex Fare): không kiểm tra được tổng tiền | 15.703.126 (17,47%) |
| `is_total_mismatch` | tổng tiền không khớp (xem bên dưới) | 384.360 (0,43%) |
| `is_location_unknown` | mã đón/trả là 264, 265 hoặc ngoài 1–265 | 797.317 (0,89%) |
| `is_flex_fare` | `payment_type = 0` | 15.703.126 (17,47%) |
| **`is_valid_for_fact`** | điều kiện giữ dòng trong Fact: trả sau đón, đón trong 2024–2025, `fare`, `total`, `distance` không âm | **85.745.246 (95,39%)** |

Tổng: 89.892.322 dòng (24 tháng, đo 18/11/2026). Một dòng có thể bật nhiều cờ.

**Về `is_total_mismatch`:** cộng thẳng các khoản thành phần cho ~28,8 triệu dòng "lệch" (32%). Phân tích cho thấy gần như toàn bộ thuộc hai quy luật của dữ liệu TLC:
1. Flex Fare (`payment_type = 0`): các cột phụ phí NULL nhưng `total` vẫn gồm phụ phí → tách thành cờ `is_surcharge_missing`.
2. Ở nhiều dòng, `extra` đã gồm sẵn phụ phí ùn tắc, CBD và/hoặc sân bay → công thức cộng hai lần (lệch đúng −2,50; −3,25; −1,75...).

Vì vậy `is_total_mismatch` chỉ bật khi `total` không khớp **bất kỳ** cách tính nào sau: tổng thành phần; trừ (ùn tắc + CBD); trừ sân bay; trừ cả ba. Đây là quy luật quan sát từ dữ liệu, không phải định nghĩa chính thức của TLC.

### `stg_taxi_zone_lookup`

`trim()` các cột chữ, giữ nguyên giá trị nguồn (kể cả `N/A`, `Unknown`), thêm `is_unknown_zone` cho mã 264 (Unknown) và 265 (Outside of NYC).

## Chạy

Container phải đang chạy và **không có pipeline Mage nào đang ghi** (DuckDB chỉ cho một tiến trình ghi).

```powershell
.\tasks.ps1 dbt-build staging        # build 2 view + chạy 13 test
.\tasks.ps1 dbt-test staging         # chỉ chạy test
```

Lệnh tương đương: `docker compose exec -T -w /home/src/dbt mage dbt build --select staging --profiles-dir .`

## Test

| Test | Kiểm tra |
|---|---|
| `not_null` | `source_file_name`, `source_row_number`, `batch_id`, `source_month`; `location_id`, `borough` của zone |
| `unique` | `stg_taxi_zone_lookup.location_id` |
| `relationships` (mức cảnh báo) | `pu_location_id`, `do_location_id` có trong Zone Lookup |
| `assert_stg_trips_match_raw` | số dòng theo từng file của staging bằng raw (staging không lọc, không nhân bản) |
| `assert_stg_trips_unique_source_row` | mỗi file có `source_row_number` liên tục 1..N (`min = 1`, `max = N`, `sum = N(N+1)/2`): bắt lỗi nạp trùng hoặc mất dòng |

Kết quả 18/11/2026 trên 24 tháng: 13/13 PASS, ~12 s. Test trùng dòng ban đầu viết bằng `GROUP BY (file, số dòng)` mất 122 s; cách kiểm tra theo `min/max/sum` cho cùng kết luận với các lỗi thực tế trong < 1 s.

## Kiểm tra nhanh

```powershell
.\tasks.ps1 sql "select count(*) tong, count(*) filter (where is_valid_for_fact) giu_lai, count(*) filter (where is_total_mismatch) lech_tien from stage.stg_yellow_taxi_trips"
```

## Profiling dữ liệu thô (`sql/profiling/`)

Các truy vấn đo lỗi trên `raw.yellow_tripdata` / `raw.taxi_zone_lookup`. Quy tắc các cờ staging lấy từ đây.

```powershell
.\tasks.ps1 profile 02_profile_errors.sql
```

`tasks.ps1 profile` chạy lần lượt mọi câu lệnh trong file và in kết quả của từng câu (qua `sql/run_sql.py`, chế độ chỉ đọc).

| File | Khảo sát | Thời gian (24 tháng) |
|---|---|---:|
| `02_profile_errors.sql` | Số dòng của từng loại lỗi; kiểm chứng 5 cột NULL trùng đúng tập Flex Fare | 10 s |
| `03_profile_by_vendor.sql` | Lỗi theo nhà cung cấp | 3 s |
| `04_profile_negative_fare.sql` | `fare_amount` âm và `total_amount` âm theo loại thanh toán | 3 s |
| `05_profile_nulls.sql` | Số dòng NULL từng cột, khoảng thời gian đón/trả | 9 s |
| `06_profile_categorical.sql` | Giá trị của các cột phân loại | 3 s |
| `07_profile_outliers.sql` | Giá trị cực đoan, vận tốc > 100 mph, phụ phí âm | 14 s |
| `08_profile_by_month.sql` | Lỗi theo từng file (tháng) | 7 s |
| `09_profile_followup.sql` | File có dòng đón ngoài kỳ; top 5 giờ "trả trước đón" ở 11/2024, 11/2025 | 3 s |
| `10_profile_duplicates.sql` | Nhóm dòng trùng hoàn toàn trong **một file** (đổi tên file ở dòng `SET VARIABLE f = ...`) | 4 s |
| `11_profile_consistency.sql` | Tổng tiền so với các khoản thành phần; thống kê và tên trùng của Zone Lookup | 4 s |

## Lưu ý

- Staging là view: đổi logic thì chạy lại `dbt build --select staging`, không cần nạp lại dữ liệu.
- `dbt` và pipeline Mage không chạy cùng lúc (khóa file DuckDB).
- dbt dùng thư mục tạm mặc định của DuckDB `data/warehouse/nyc_taxi.duckdb.tmp` (dbt-duckdb không cho đặt `temp_directory` qua `settings`).
