# Power BI: dựng báo cáo từ OLAP mart

Luồng dữ liệu:

```text
DuckDB (olap.*, dds.dim*) ──export-bi──> data/bi/*.parquet ──Power Query──> Power BI model ──> báo cáo
                                         powerbi/map_shapes/ (TopoJSON, tâm khu vực)
```

Power BI không đọc trực tiếp file DuckDB (cần cài thêm ODBC driver, và khi Power BI giữ kết nối thì Mage/dbt không ghi được). Vì vậy dữ liệu được xuất ra Parquet, đọc bằng connector Parquet có sẵn của Power BI Desktop. Fact (~85 triệu dòng) không được xuất: báo cáo dùng 5 mart đã tổng hợp (xem [olap.md](olap.md)).

File trong repo:

| File | Nội dung |
|---|---|
| `powerbi/scripts/export_bi.py` | Xuất 5 mart + 7 Dimension ra `data/bi/*.parquet` (+ `_manifest.json`), chế độ read_only |
| `powerbi/scripts/build_map_shapes.py` | Shapefile `data/reference/taxi_zones.zip` → `powerbi/map_shapes/taxi_zones.topojson` + `taxi_zone_centroids.csv` (đã commit sẵn, chỉ chạy lại khi shapefile đổi) |
| `powerbi/queries/*.pq` | Truy vấn Power Query (M), mỗi file một bảng |
| `powerbi/dax/measures.dax` | Toàn bộ measure DAX, dạng `DEFINE MEASURE` cho DAX query view |

## 1. Xuất dữ liệu

Chạy sau mỗi lần pipeline (ingest → `dbt build`) có dữ liệu mới, khi không có pipeline nào đang ghi:

```powershell
.\tasks.ps1 export-bi        # ~5 s, ghi data/bi/ (không commit)
.\tasks.ps1 build-map        # chỉ khi cần dựng lại file bản đồ (cần internet lần đầu để cài extension spatial)
```

Kết quả 18/11/2026: 12 file, ~110 MB (`mart_trips_daily` 64 MB, `mart_routes_monthly` 40 MB, còn lại < 4 MB).

## 2. Dựng model trong Power BI Desktop

### 2.1 Tham số và truy vấn
1. **Home > Transform data** để mở Power Query Editor.
2. **Manage Parameters > New Parameter**: tên `RepoFolder`, Type `Text`, Current value = thư mục gốc repo trên máy bạn, ví dụ `D:\DEADLINE\DATA_ENGINEER\DE_TO_CV` (không có `\` ở cuối). Nội dung tương đương ở `powerbi/queries/RepoFolder.pq`.
3. Với mỗi file còn lại trong `powerbi/queries/`: **New Source > Blank Query**, đổi tên query đúng bằng tên file (vd `TripsDaily`), mở **Advanced Editor**, dán nội dung file. Thứ tự: `DimDate` trước `DimMonth` (DimMonth đọc từ DimDate).
4. **Close & Apply**. Kiểm tra số dòng (cột phải dưới cùng ở Table view) so với `data/bi/_manifest.json`; riêng `DimDate` ít hơn 1 dòng (đã bỏ dòng Unknown).

| Query | Nguồn | Xử lý thêm trong M |
|---|---|---|
| `DimDate` | `dimdate.parquet` | Bỏ dòng Unknown (`datesk = -1`); thêm `monthkey = year*100 + month` |
| `DimMonth` | từ `DimDate` | Một dòng mỗi tháng: `monthkey`, `year`, `quarter`, `month`, `monthname`, `monthstart`, `yearmonth`, `monthshort` (Jan…Dec) |
| `DimLocation` | `dimlocation.parquet` + `taxi_zone_centroids.csv` | Thêm `latitude`, `longitude` |
| `DimPaymentType` | `dimpaymenttype.parquet` | Thêm `paymentorder` (thứ tự hiển thị; Unknown cuối) |
| `DimPassengerGroup` | `dimpassengergroup.parquet` | Thêm `passengerorder` (No passenger count, Unknown cuối) |
| `DimVendor`, `DimRateCode`, `DimDistanceGroup` | `dim*.parquet` | |
| `TripsDaily`, `HourlyActivity` | `mart_trips_daily`, `mart_hourly_activity` | |
| `RoutesMonthly` | `mart_routes_monthly` | Thêm `monthkey`, `route` = "khu vực đón → khu vực trả" |
| `TripProfile`, `MonthlyKPI` | `mart_trip_profile`, `mart_monthly_kpi` | Thêm `monthkey` |
| `RevenueComponent` | bảng tĩnh trong M (không đọc file) | 8 khoản doanh thu + `componentorder`, cho waterfall trang 7; **không tạo quan hệ** |
| `DataFreshness` (tùy chọn) | `data/bi/_manifest.json` | Một dòng: thời điểm xuất dữ liệu (UTC và giờ VN), cho card "Data as of" (mục 6); **không tạo quan hệ** |

### 2.2 Quan hệ (Model view)

Tất cả là một-nhiều (1 → *), lọc một chiều từ Dimension sang mart. Tắt **Autodetect relationships** (File > Options > Current file > Data load) để Power BI không tự nối sai, rồi tạo tay:

| Từ (1) | Đến (*) | Ghi chú |
|---|---|---|
| `DimMonth[monthkey]` | `DimDate[monthkey]` | Slicer Năm/Tháng lọc DimDate, từ đó lọc mart ngày |
| `DimMonth[monthkey]` | `RoutesMonthly[monthkey]`, `TripProfile[monthkey]`, `MonthlyKPI[monthkey]` | |
| `DimDate[datesk]` | `TripsDaily[datesk]`, `HourlyActivity[datesk]` | |
| `DimLocation[locationsk]` | `TripsDaily[locationsk]` | |
| `DimLocation[locationsk]` | `RoutesMonthly[pickup_locationsk]` | Active |
| `DimLocation[locationsk]` | `RoutesMonthly[dropoff_locationsk]` | **Inactive** (measure `Zone Dropoffs` bật bằng `USERELATIONSHIP`) |
| `DimVendor[vendorsk]` | `TripsDaily[vendorsk]` | |
| `DimPaymentType[paymenttypesk]` | `TripsDaily[paymenttypesk]`, `TripProfile[paymenttypesk]` | |
| `DimRateCode[ratecodesk]` | `TripsDaily[ratecodesk]`, `TripProfile[ratecodesk]` | |
| `DimPassengerGroup[passengergroupsk]` | `TripProfile[passengergroupsk]` | |
| `DimDistanceGroup[distancegroupsk]` | `TripProfile[distancegroupsk]` | |

`HourlyActivity` có cột `borough` riêng (quận của điểm đón hoặc trả theo vai trò), không nối DimLocation.

### 2.3 Thiết lập cột
- **Mark as date table:** chọn `DimDate` > Table tools > Mark as date table > cột `fulldate` (cần cho `Revenue PM`, `Revenue PY`).
- **Sort by column:** `DimDate[monthname]`, `DimMonth[monthname]` và `DimMonth[monthshort]` theo `month`; `DimDate[dayname]` và `HourlyActivity[dayname]` theo `dayofweek`; `HourlyActivity[monthname]` theo `month`; `HourlyActivity[timeslot]` theo `hour`; `DimMonth[yearmonth]` theo `monthkey`; `DimPaymentType[paymenttypename]` theo `paymentorder`; `DimPassengerGroup[passengergroupname]` theo `passengerorder`; `DimDistanceGroup[distancegroupname]` theo `distancegroupsk`; `RevenueComponent[component]` theo `componentorder`.
- **Ẩn** (Hide in report view) mọi cột `*sk`, `monthkey`, và các cột thuộc tính trùng trong mart (`year`, `month`, `borough`, `vendorname`... của `TripsDaily`) để người xem luôn dùng cột của Dimension: tránh slicer chỉ lọc được một mart.
- **Data category:** `DimLocation[latitude]` = Latitude, `[longitude]` = Longitude; `DimLocation[borough]` = State or Province (tùy chọn).

### 2.4 Measure
1. Mở **DAX query view** (biểu tượng thứ tư ở thanh bên trái).
2. Dán toàn bộ `powerbi/dax/measures.dax`, bấm **Run**: kết quả `EVALUATE` cuối file phải là `Trips` = 85.745.246 (bằng `Profile Trips`, `Route Trips`, `Pickup Trips`, `KPI Trips`).
3. Bấm **Update model with changes** để thêm toàn bộ measure vào model.
4. Đặt định dạng (Measure tools > Format): `%` cho các measure có `%`, `Share`, `Tip Rate`; tiền tệ USD cho `Revenue`, `Amount`, `per Trip` (tiền); số nguyên có dấu phân cách cho `Trips`, `Passengers`.

## 3. Các trang báo cáo

> Bảng dưới đây là phác thảo ban đầu. Bản dựng cuối nằm trong template `powerbi/dashboard/NYC_Taxi_Dashboard.pbit`; khi hai nơi khác nhau, theo template.

Slicer chung đặt ở mọi trang (Sync slicers): `DimMonth[year]`, `DimMonth[yearmonth]` (hoặc `month`).

| Trang | Câu | Visual gợi ý |
|---|---|---|
| **1. Tổng quan** | A1, A6, A8 | Thẻ KPI: `Trips`, `Passengers`, `Revenue`, `Avg Revenue per Trip`; biểu đồ đường `Trips` và `Passengers` theo `DimDate[fulldate]` (drill-down Năm → Tháng → Ngày: tạo hierarchy `year` > `month` > `fulldate` trong DimDate); bảng theo `DimLocation[borough]` (A6: `Trips`, `Passengers`, `Revenue`, `Avg Revenue per Trip`) |
| **2. Doanh thu khu vực & hãng** | A2, 5b | Matrix: hàng `DimLocation[borough]` > `zone` (drill-down Zone → Borough), cột `DimVendor[vendorname]`, giá trị `Revenue`; biểu đồ vùng `Pickup Revenue` theo `HourlyActivity[hour]`, chú giải `HourlyActivity[borough]` (5b), slicer `HourlyActivity[timeslot]` |
| **3. Thanh toán** | A3 | Biểu đồ cột chồng 100%: trục `DimMonth[yearmonth]`, chú giải `DimPaymentType[paymenttypename]`, giá trị `Trips`; slicer `DimLocation[borough]` |
| **4. Thời điểm đón/trả** | A4 | Biểu đồ cột cụm `Pickup Trips`, `Dropoff Trips` theo `HourlyActivity[hour]`; ma trận nhiệt (Matrix + conditional formatting): hàng `DimDate[dayname]` (cột `HourlyActivity[dayname]` đã ẩn ở 2.3; `datesk` của mart giờ là ngày đón hoặc ngày trả theo vai trò nên vẫn đúng), cột `HourlyActivity[hour]`, giá trị `Pickup Trips` |
| **5. Hồ sơ chuyến đi** | A5, B1 | Matrix: hàng `DimPassengerGroup[passengergroupname]`, cột `DimDistanceGroup[distancegroupname]`, giá trị `Profile Trips`, slicer `DimRateCode[ratecodename]` (A5); biểu đồ kết hợp theo `DimRateCode[ratecodename]`: cột `Profile Avg Tip Rate`, đường `Profile Avg Speed (mph)` (B1) |
| **6. Tuyến & bản đồ** | A7, B5 | Bảng `RoutesMonthly[route]`, `Route Trips`, `Route Avg Duration (min)` (không dùng `Route Avg Distance (mi)`: có quãng đường bất thường), `Route Revenue`, lọc visual Top N = 10 theo `Route Trips` (hoặc `Route Rank` ≤ 10); Shape map lượt đón/trả theo khu vực (mục 4) |
| **7. Xu hướng & so sánh kỳ** | B2, B3, B4 | Biểu đồ đường `KPI Revenue` và `KPI Trips` theo `DimMonth[yearmonth]`; cột `KPI Revenue YoY %` (B4); thẻ `Revenue May`, `Revenue June`, `Revenue June vs May %` với slicer năm, kèm bảng theo `DimVendor`/`DimRateCode`/`DimLocation[borough]` dùng các measure đó (B2); biểu đồ đường `Fare per Trip`, `Surcharges per Trip`, `Tip per Trip`, `Avg Distance per Trip (mi)` theo tháng (B3: doanh thu/chuyến tăng do thành phần nào). Bản dựng cuối dùng measure của `TripsDaily` (slicer Borough có tác dụng) và waterfall `Component per Trip Change` theo bảng `RevenueComponent` thay cho các đường theo tháng |

## 4. Bản đồ Taxi Zone (B5)

**Shape map** (tô màu từng khu vực):
1. File > Options > Preview features: bật **Shape map visual**, khởi động lại Power BI nếu được yêu cầu.
2. Thêm visual Shape map: **Location** = `DimLocation[locationid]`, **Color saturation** = `Zone Pickups` (hoặc `Zone Dropoffs`, `Zone Net Inflow`).
3. Format > Map settings > Map type: **Custom map** > Add map type: chọn `powerbi/map_shapes/taxi_zones.topojson`.
4. Mục **View map keys** phải hiện danh sách `LocationID`; nếu khóa không khớp (bản đồ xám), đổi Location sang `DimLocation[locationid]` kiểu Text.

**Bản đồ bong bóng** (thay thế, không cần preview): visual Map hoặc Azure Map, Latitude = `DimLocation[latitude]`, Longitude = `DimLocation[longitude]`, Size = `Zone Pickups`, Tooltips = `zone`, `borough`.

Mã 264 (Unknown) và 265 (Outside of NYC) không có hình nên không hiện trên bản đồ (~0,9% chuyến đi).

## 5. Đối chiếu số liệu

Sau khi dựng xong, kiểm tra các giá trị sau (tính từ DuckDB ngày 18/11/2026, toàn kỳ 2024–2025, không lọc):

| Kiểm tra | Giá trị đúng |
|---|---|
| `Trips` (= `Profile Trips` = `Route Trips` = `Pickup Trips` = `KPI Trips`) | 85.745.246 |
| `Revenue` | 2.475.529.050,41 USD |
| `Avg Revenue per Trip` | 28,87 USD |
| `Avg Speed (mph)` | 10,94 |
| `Avg Tip Rate` | 21,88% |
| `Revenue` theo quận | Manhattan 1.821,55 triệu; Queens 559,73 triệu; Brooklyn 66,30 triệu |
| `Trips` theo thanh toán | Credit card 61.037.820; Unknown 13.525.379; Cash 9.776.108 |
| Giờ cao điểm đón (`Pickup Trips`) | 18h: 6.121.334; 17h: 5.831.083 |
| Khu vực đón nhiều nhất (`Zone Pickups`) | 237 Upper East Side South 3.914.225; 161 Midtown Center 3.861.733; 132 JFK Airport 3.826.639 |
| B2 năm 2025 | `Revenue May` 123.319.399,64; `Revenue June` 117.898.926,26; `Revenue June vs May %` −4,40% |
| B2 năm 2024 | `Revenue May` 106.909.224,54; `Revenue June` 100.121.367,53; −6,35% |
| B1 (`Profile Avg Tip Rate`, `Profile Avg Speed (mph)`) | Standard rate 23,69%, 10,19 mph; JFK 20,03%, 22,29 mph |

Lệch so với bảng này thường do: thiếu quan hệ hoặc quan hệ sai chiều, slicer đang lọc, hoặc cộng `HourlyActivity` không lọc vai trò.

## 6. Lưu và cập nhật

- **Refresh** sau khi pipeline chạy lại (`.\tasks.ps1 e2e`, hoặc chỉ `.\tasks.ps1 export-bi`): Home > Refresh trong Power BI.
- **Card "Data as of"** (tùy chọn, cho người xem biết dữ liệu mới đến đâu). Truy vấn `powerbi/queries/DataFreshness.pq` đọc `exported_at_utc` trong `data/bi/_manifest.json`, giá trị do bước cuối của pipeline ghi.
  1. Transform data > New Source > Blank Query, đặt tên `DataFreshness`, dán nội dung file, Close & Apply. **Không tạo quan hệ.**
  2. Tạo measure này **trong bảng `DataFreshness`**: ở pane Data, chuột phải `DataFreshness` > **New measure**, dán công thức. Measure không nằm trong `measures.dax`, vì nếu dán cả file vào model chưa có bảng `DataFreshness` thì sẽ báo lỗi:
     ```dax
     Data As Of = "Data as of " & FORMAT ( MAX ( DataFreshness[exported_at_local] ), "yyyy-mm-dd HH:mm" ) & " (UTC+7)"
     ```
  3. Đặt Card ở góc trên bên phải mỗi trang, chỗ trống ngang hàng tiêu đề trang: Format > General > Properties: X `1024`, Y `16`, Width `240`, Height `36`. Tắt nền, viền, nhãn category; giá trị căn phải, chữ 9 pt, màu `#8A94A3`. Mép phải (1264) thẳng với mép phải các bảng rộng 1048 px. Làm ở một trang rồi copy (Ctrl+C / Ctrl+V) sang các trang khác; Power BI giữ nguyên vị trí. Không đặt ở cuối thanh bên trái: ô ghi chú đã chiếm từ y 552 đến hết trang.
- **Lưu file:** `powerbi/dashboard/NYC_Taxi_Dashboard.pbix` chứa cả dữ liệu đã nạp (khoảng 125 MB, vượt giới hạn 100 MB của GitHub) và bị `.gitignore` bỏ qua. File đưa vào git là template **File > Export > Power BI template**: `powerbi/dashboard/NYC_Taxi_Dashboard.pbit` (khoảng 330 KB: chỉ model, truy vấn, measure, báo cáo, không có dữ liệu). Mở `.pbit` thì Power BI hỏi `RepoFolder` (thư mục gốc repo), rồi nạp lại từ `data/bi/*.parquet`, nên cần chạy `.\tasks.ps1 export-bi` trước.
