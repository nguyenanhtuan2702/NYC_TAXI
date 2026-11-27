# OLAP mart (schema `olap`)

Các bảng tổng hợp từ `dds.facttaxitrip` cho Power BI, xây bằng dbt (`dbt/models/olap_marts/`, materialized `table`). Mỗi mart phục vụ nhiều câu hỏi trong `docs/data_modeling/modeling.pdf` (mục 6), thay vì mỗi câu một bảng: ít logic trùng lặp, Power BI vẫn slice/dice tự do trong từng mart.

## Các mart

| Mart | Grain (một dòng là) | Số dòng (24 tháng) | Câu hỏi |
|---|---|---:|---|
| `mart_trips_daily` (basic) | ngày đón × khu vực đón × hãng xe × hình thức thanh toán × mã giá | 1.411.379 | A1, A2 (ngày/tháng/năm), A3, A6, A8, B2, B3 |
| `mart_hourly_activity` (basic) | vai trò (`pickup`/`dropoff`) × ngày × giờ × quận | 242.110 | A4, A2 (mức giờ), 5b |
| `mart_routes_monthly` (basic) | tháng × khu vực đón × khu vực trả | 823.930 | A7, B5 |
| `mart_trip_profile` (basic) | tháng × nhóm hành khách × mã giá × nhóm cự ly × thanh toán | 5.264 | A5, B1, B3 |
| `mart_monthly_kpi` (advanced) | tháng đón | 24 | B2, B3, B4 |

Mart dùng thuộc tính Dimension **tại thời điểm chuyến đi** (DimLocation là SCD2, nối theo SK), và giữ cả SK để nối lại Dimension trong Power BI khi cần.

### Câu hỏi → cách dùng

| Câu | Mart | Gợi ý |
|---|---|---|
| A1 Chuyến, hành khách theo ngày → tháng → năm | `mart_trips_daily` | `sum(total_trips)`, `sum(total_passengers)` theo `fulldate`/`month`/`year` |
| A2 Doanh thu quận/zone × hãng × thời điểm | `mart_trips_daily`; giờ: `mart_hourly_activity` (`pickup`) | `sum(total_revenue)` theo `borough`/`zone`, `vendorname` |
| A3 Chuyến theo thanh toán × quận × tháng | `mart_trips_daily` | `paymenttypename`, `borough`, `month` |
| A4 Đón/trả theo giờ, thứ, tháng | `mart_hourly_activity` | lọc `activity_role`; `hour`/`timeslot`, `dayname`, `month` |
| A5 Nhóm khách × mã giá × nhóm cự ly | `mart_trip_profile` | `passengergroupname`, `ratecodename`, `distancegroupname` |
| A6 Dashboard theo quận | `mart_trips_daily` | chuyến, hành khách, doanh thu, doanh thu/chuyến |
| A7 Top N tuyến | `mart_routes_monthly` | `sum(total_trips)` theo (`pickup_zone`, `dropoff_zone`), sắp giảm dần |
| A8 Tổng doanh thu | `mart_trips_daily` hoặc `mart_monthly_kpi` | `sum(total_revenue)` |
| B1 Tỷ lệ boa, vận tốc theo mã giá | `mart_trip_profile` | xem công thức bên dưới |
| B2 Tháng 5 so với tháng 6 | `mart_monthly_kpi` (tổng), `mart_trips_daily` (yếu tố: hãng, khu vực, mã giá, các khoản phí) | `revenue_growth_mom` |
| B3 Doanh thu tăng, số chuyến gần như không đổi | `mart_monthly_kpi` | `avg_revenue_per_trip`, `avg_fare_per_trip`, `avg_surcharges_per_trip`, `avg_distance_per_trip`; chi tiết theo mã giá/cự ly: `mart_trip_profile` |
| B4 So sánh cùng kỳ | `mart_monthly_kpi` | `trip_growth_yoy`, `revenue_growth_yoy` (2025 so với 2024) |
| B5 Bản đồ đón/trả theo Taxi Zone | `mart_routes_monthly` | cộng theo `pickup_locationid` hoặc `dropoff_locationid`; nối Taxi Zone Boundaries bằng LocationID ở Power BI |
| 5b Doanh thu quận × tháng × khung giờ | `mart_hourly_activity` (`pickup`) | `borough`, `month`, `hour`/`timeslot` |

## Measure

Mọi mart (trừ `mart_hourly_activity`, chỉ có chuyến, hành khách, doanh thu) có cùng bộ cột từ macro `dbt/macros/olap_trip_measures.sql`. Mart **chỉ lưu các tổng cộng dồn được**, đúng phần "Measures bổ sung" của modeling.pdf; giá trị trung bình phải tính lại sau khi gộp nhóm, không lấy trung bình của trung bình.

| Cột | Ý nghĩa |
|---|---|
| `total_trips`, `total_passengers` | Số chuyến, tổng hành khách (BIGINT) |
| `valid_passenger_trips` | Chuyến có `passenger_count > 0` |
| `total_distance`, `valid_distance_trips` | Tổng quãng đường; chuyến có quãng đường > 0 |
| `total_duration_minutes`, `valid_duration_trips` | Tổng thời lượng; chuyến có thời lượng > 0 |
| `valid_speed_trips`, `sum_trip_speed` | Chuyến có vận tốc hợp lệ (quãng đường, thời lượng > 0, ≤ 100 mph) và tổng vận tốc từng chuyến |
| `valid_tip_rate_trips`, `sum_trip_tip_rate` | Chuyến thẻ tín dụng có cước > 0, tổng tỷ lệ boa từng chuyến |
| `credit_tip_amount`, `credit_fare_amount` | Tổng boa, tổng cước của các chuyến trên |
| `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `congestion_surcharge`, `airport_fee`, `cbd_congestion_fee` | Tổng từng khoản tiền |
| `total_revenue` | Tổng `TotalAmount` |

Công thức trung bình (DAX hoặc SQL):

```
AvgRevenuePerTrip   = sum(total_revenue) / sum(total_trips)
AvgPassengersPerTrip= sum(total_passengers) / sum(valid_passenger_trips)
AvgDistancePerTrip  = sum(total_distance) / sum(valid_distance_trips)
AvgTripDuration     = sum(total_duration_minutes) / sum(valid_duration_trips)
AvgSpeed (từng chuyến, modeling.pdf trang 4) = sum(sum_trip_speed) / sum(valid_speed_trips)
AvgTipRate (tổng thể, câu B1)                = sum(credit_tip_amount) / sum(credit_fare_amount)
```

`mart_monthly_kpi` tính sẵn các trung bình trên ở mức tháng (`avg_*`) và tăng trưởng: `prev_month_*`, `trip_growth_mom`, `revenue_growth_mom`, `same_month_ly_*`, `trip_growth_yoy`, `revenue_growth_yoy`. Tháng trước và cùng kỳ năm trước tìm bằng phép nối theo ngày đầu tháng; tháng đầu tiên (01/2024) và năm 2024 có giá trị so sánh NULL.

**Lưu ý khi cộng `mart_hourly_activity`:** mỗi chuyến xuất hiện hai lần (một dòng `pickup`, một dòng `dropoff`). Luôn lọc một vai trò trước khi cộng doanh thu.

## Chạy và kiểm thử

```powershell
.\tasks.ps1 dbt-build olap_marts       # 5 mart + test (~1,5 phút)
.\tasks.ps1 dbt-build                   # toàn bộ pipeline dbt (snapshot → staging → DDS → OLAP)
```

Test: `models/olap_marts/schema.yml` (NOT NULL, `accepted_values` cho `activity_role`, `month_start` duy nhất) và `tests/olap/assert_olap_marts_reconcile_fact.sql`: tổng số chuyến, hành khách bằng Fact và doanh thu lệch < 1 USD ở mọi mart (mart giờ kiểm tra từng vai trò).

## Kết quả 18/11/2026 (24 tháng)

- Tổng: 85.745.246 chuyến, doanh thu 2.475.529.050,41 USD; khớp ở cả 5 mart.
- Mẫu `mart_monthly_kpi`: mỗi tháng 2,9–4,2 triệu chuyến, doanh thu/chuyến 26,7–31,7 USD; tháng 12/2025 doanh thu tăng 25,6% so với 12/2024.
- B1 (`mart_trip_profile`): tỷ lệ boa Standard rate 23,69%, JFK 20,03%; vận tốc trung bình Standard 10,2 mph, JFK 22,3 mph, Nassau/Westchester 29,5 mph.
- Quan sát dữ liệu: mã giá Unknown (99, chủ yếu Flex Fare) có tỷ lệ boa 0% trên các chuyến thẻ; Group ride chỉ 118 chuyến nên tỷ lệ boa (267%) không có ý nghĩa thống kê.
