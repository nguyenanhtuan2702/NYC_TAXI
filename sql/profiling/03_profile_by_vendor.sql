-- =====================================================================
-- THỐNG KÊ THEO TỪNG VENDOR_ID trên bảng staging
-- Mỗi dòng kết quả = một vendor_id (kể cả NULL nếu có).
-- Mỗi cột = số dòng thỏa một điều kiện trong vendor đó.
-- =====================================================================
SELECT
  -- Mã vendor, dùng để nhóm kết quả
  vendor_id,
  -- Tổng số dòng của vendor này
  count(*)                                              AS so_dong,
  -- Đếm dòng thiếu số hành khách
  count(*) FILTER (WHERE passenger_count IS NULL)       AS pax_null,
  -- Đếm dòng có payment_type = 0
  count(*) FILTER (WHERE payment_type = 0)              AS pay_0,
  -- Đếm dòng thiếu ratecode_id
  count(*) FILTER (WHERE ratecode_id IS NULL)           AS rate_null,
  -- Đếm dòng bị cả 3 lỗi cùng lúc: thiếu số hành khách, payment_type = 0 và thiếu ratecode_id
  count(*) FILTER (WHERE passenger_count IS NULL
                     AND payment_type = 0
                     AND ratecode_id IS NULL)           AS ca_ba_cung_luc,
  -- Đếm dòng có tiền cước âm
  count(*) FILTER (WHERE fare_amount < 0)               AS fare_am,
  -- Đếm dòng có tổng tiền âm
  count(*) FILTER (WHERE total_amount < 0)              AS total_am
FROM stage.stg_yellow_taxi_trips   -- bảng staging
GROUP BY vendor_id                 -- gom nhóm theo vendor
ORDER BY vendor_id;                -- sắp xếp theo mã vendor tăng dần