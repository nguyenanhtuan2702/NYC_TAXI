-- TRUY VẤN KIỂM TRA TRÊN BẢNG STAGING

-- TRUY VẤN 1: giờ đón sớm nhất + số dòng có phí cải thiện âm 
SELECT
  -- Giờ đón sớm nhất trong toàn bảng
  min(tpep_pickup_datetime) AS pickup_min,
  -- Đếm dòng có phí cải thiện dịch vụ (improvement_surcharge) âm
  count(*) FILTER (WHERE improvement_surcharge < 0) AS improvement_am
FROM stage.stg_yellow_taxi_trips;   -- bảng staging


-- TRUY VẤN 2: các file nguồn có dòng đón ngoài kỳ 2024-2025
-- Với mỗi file, đếm số dòng có giờ đón trước 01/01/2024 hoặc từ 01/01/2026 trở đi
SELECT
  source_file_name,         -- tên file nguồn
  count(*) AS so_dong       -- số dòng ngoài kỳ trong file đó
FROM stage.stg_yellow_taxi_trips
WHERE tpep_pickup_datetime < '2024-01-01'
   OR tpep_pickup_datetime >= '2026-01-01'   -- chỉ giữ các dòng đón ngoài kỳ
GROUP BY 1    -- gom nhóm theo cột đầu tiên (source_file_name)
ORDER BY 1;   -- sắp xếp theo tên file


-- TRUY VẤN 3: top 5 giờ có nhiều chuyến "trả trước đón" nhất
-- Chỉ xét 2 file: tháng 11/2024 và tháng 11/2025
-- Chỉ xét các dòng có giờ trả sớm hơn giờ đón
SELECT
  -- Cắt giờ đón về đầu giờ (ví dụ 14:35:20 -> 14:00:00) để gom theo từng giờ
  date_trunc('hour', tpep_pickup_datetime) AS gio_don,
  -- Số dòng "trả trước đón" trong giờ đó
  count(*) AS so_dong
FROM stage.stg_yellow_taxi_trips
WHERE source_file_name IN ('yellow_tripdata_2024-11.parquet','yellow_tripdata_2025-11.parquet')
  AND tpep_dropoff_datetime < tpep_pickup_datetime   -- giờ trả sớm hơn giờ đón
GROUP BY 1       -- gom nhóm theo gio_don
ORDER BY 2 DESC  -- sắp xếp theo so_dong (cột thứ 2) giảm dần: giờ nhiều nhất lên đầu
LIMIT 5;         -- chỉ lấy 5 dòng đầu