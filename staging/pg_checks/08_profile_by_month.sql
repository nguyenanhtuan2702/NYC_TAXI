-- THỐNG KÊ LỖI THEO TỪNG FILE NGUỒN (bảng staging)
-- Mỗi dòng kết quả = một file nguồn (source_file_name).
-- Mỗi cột = số dòng thỏa một điều kiện trong file đó.
-- Dùng để xem lỗi tập trung ở file nào.
SELECT
  -- Tên file nguồn, dùng để nhóm kết quả
  source_file_name,
  -- Đếm dòng có payment_type = 0
  count(*) FILTER (WHERE payment_type = 0) AS pay_0,
  -- Đếm dòng thiếu số hành khách
  count(*) FILTER (WHERE passenger_count IS NULL) AS pax_null,
  -- Đếm dòng có vendor_id khác 1 và 2 (dòng NULL không được đếm ở đây)
  count(*) FILTER (WHERE vendor_id NOT IN (1,2)) AS vendor_la,
  -- Đếm dòng có tiền cước âm
  count(*) FILTER (WHERE fare_amount < 0) AS fare_am,
  -- Đếm dòng có quãng đường nhỏ hơn hoặc bằng 0
  count(*) FILTER (WHERE trip_distance <= 0) AS dist_le_0,
  -- Đếm dòng có giờ trả sớm hơn giờ đón
  count(*) FILTER (WHERE tpep_dropoff_datetime < tpep_pickup_datetime) AS drop_truoc
FROM stage.stg_yellow_taxi_trips   -- bảng staging
GROUP BY 1                         -- gom nhóm theo cột đầu tiên trong SELECT (source_file_name)
ORDER BY 1;                        -- sắp xếp theo cột đầu tiên (source_file_name) tăng dần