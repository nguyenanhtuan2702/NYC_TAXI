-- THỐNG KÊ THEO TỪNG PAYMENT_TYPE trên bảng staging
-- Mỗi dòng kết quả = một payment_type (kể cả NULL nếu có).
-- Mỗi cột = số dòng thỏa một điều kiện trong nhóm thanh toán đó.
SELECT
  -- Mã hình thức thanh toán, dùng để nhóm kết quả
  payment_type,
  -- Tổng số dòng của hình thức thanh toán này
  count(*)                                                    AS so_dong,
  -- Đếm dòng có tiền cước âm
  count(*) FILTER (WHERE fare_amount < 0)                     AS fare_am,
  -- Đếm dòng có tổng tiền âm
  count(*) FILTER (WHERE total_amount < 0)                    AS total_am,
  -- Đếm dòng có tiền cước âm nhưng tổng tiền không âm (>= 0)
  count(*) FILTER (WHERE fare_amount < 0 AND total_amount >= 0) AS fare_am_total_khong_am
FROM stage.stg_yellow_taxi_trips   -- bảng staging
GROUP BY payment_type              -- gom nhóm theo hình thức thanh toán
ORDER BY payment_type;             -- sắp xếp theo mã thanh toán tăng dần