-- Xem mỗi cột có những giá trị nào và mỗi giá trị có bao nhiêu dòng.
-- 5 cột kiểm tra: vendor_id, ratecode_id, payment_type,
--                 store_and_fwd_flag, passenger_count
-- Kết quả có 3 cột: cot (tên cột), gia_tri (giá trị), so_dong (số dòng)
SELECT
  -- GROUPING(...) cho biết dòng kết quả này đang đếm theo cột nào.
  -- Mỗi cột ứng với một con số cố định, CASE đổi con số đó thành tên cột:
  --   15 = vendor_id | 23 = ratecode_id | 27 = payment_type
  --   29 = store_and_fwd_flag | 30 = passenger_count
  CASE GROUPING(vendor_id, ratecode_id, payment_type, store_and_fwd_flag, passenger_count)
    WHEN 15 THEN 'vendor_id' WHEN 23 THEN 'ratecode_id' WHEN 27 THEN 'payment_type'
    WHEN 29 THEN 'store_and_fwd_flag' WHEN 30 THEN 'passenger_count' END AS cot,

  -- Giá trị của cột đang đếm. Ở mỗi dòng chỉ có 1 cột có giá trị,
  -- 4 cột còn lại là NULL, nên COALESCE lấy cột nào có giá trị.
  -- Nếu giá trị gốc là NULL thì hiện chữ 'NULL'.
  COALESCE(vendor_id::text, ratecode_id::text, payment_type::text,
           store_and_fwd_flag, passenger_count::text, 'NULL') AS gia_tri,

  -- Số dòng có giá trị đó
  count(*) AS so_dong
FROM stage.stg_yellow_taxi_trips   -- bảng staging

-- Đếm riêng từng cột, không kết hợp các cột với nhau
GROUP BY GROUPING SETS ((vendor_id), (ratecode_id), (payment_type),
                        (store_and_fwd_flag), (passenger_count))

-- Sắp xếp theo tên cột, rồi theo giá trị
-- (gia_tri là chữ nên '10' sẽ đứng trước '2')
ORDER BY cot, gia_tri;